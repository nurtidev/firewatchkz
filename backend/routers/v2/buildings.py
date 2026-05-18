"""
routers/v2/buildings.py — Buildings endpoints (API v2, H-6).

GET /api/v2/buildings
  Query: city (required), bbox (optional), min_risk (float, optional),
         limit (50), offset (0)
  Auth: require_inspector_or_above
  Returns: list of buildings with their latest risk_score

GET /api/v2/buildings/{building_id}
  Auth: require_inspector_or_above
  Returns: full building details + latest risk_score + shap_values

GET /api/v2/buildings/{building_id}/risk
  Query: horizon (int, 7|30|90, default 30)
  Auth: require_inspector_or_above
  Returns: {baseline_score, dynamic_modifier, final_score, horizon_days, expected_incidents}

GET /api/v2/buildings/{building_id}/factors
  Auth: require_inspector_or_above
  Returns: {shap_factors: [...top-5...], explanation: "Russian text from Claude Haiku"}
  Cache: 24h in-memory dict keyed by building_id
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_inspector_or_above

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Frontend-shape helper.
# ---------------------------------------------------------------------------
# С миграции 0009 у buildings есть name/district/object_type + details JSONB,
# в который сидер положил все «богатые» поля. Эндпоинты /buildings и
# /buildings/{id} склеивают типизированные колонки и details обратно в форму,
# ожидаемую фронтом (lib/types.ts → Building). Auth не требуется (QR-сценарий).


def _row_to_frontend_building(row: Dict[str, Any]) -> Dict[str, Any]:
    """Преобразовать строку DB в форму frontend Building."""
    details = row.get("details") or {}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {}

    # Базовые поля поверх details (типизированные колонки — приоритет)
    return {
        **details,
        "id": row["id"],
        "city": row["city_id"],
        "address": row.get("address"),
        "name": row.get("name"),
        "district": row.get("district"),
        "object_type": row.get("object_type"),
        "floors_count": row.get("floors_above"),
        "total_area": float(row["total_area_sqm"]) if row.get("total_area_sqm") is not None else None,
        "lat": float(row["lat"]) if row.get("lat") is not None else None,
        "lon": float(row["lon"]) if row.get("lon") is not None else None,
    }

# ---------------------------------------------------------------------------
# 24-hour in-memory factors cache  {building_id: {"ts": float, "data": dict}}
# ---------------------------------------------------------------------------

_FACTORS_CACHE: Dict[str, Dict[str, Any]] = {}
_FACTORS_TTL = 86_400  # 24 hours in seconds


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class RiskScoreOut(BaseModel):
    baseline_score: Optional[float]
    dynamic_modifier: Optional[float]
    final_score: Optional[float]
    score_date: Optional[str]


class BuildingListItem(BaseModel):
    id: str
    city_id: str
    address: Optional[str]
    building_type: Optional[str]
    floors_above: Optional[int]
    floors_below: Optional[int]
    total_area_sqm: Optional[float]
    year_built: Optional[int]
    risk: Optional[RiskScoreOut]


class BuildingDetail(BaseModel):
    id: str
    city_id: str
    address: Optional[str]
    building_type: Optional[str]
    floors_above: Optional[int]
    floors_below: Optional[int]
    total_area_sqm: Optional[float]
    year_built: Optional[int]
    risk: Optional[RiskScoreOut]
    shap_values: Optional[List[Dict[str, Any]]]


class RiskHorizonOut(BaseModel):
    baseline_score: float
    dynamic_modifier: float
    final_score: float
    horizon_days: int
    expected_incidents: float


class ShapFactor(BaseModel):
    feature: str
    value: Optional[float]
    shap_value: float


class FactorsOut(BaseModel):
    shap_factors: List[ShapFactor]
    explanation: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_bbox(bbox: str) -> tuple:
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=422,
            detail="bbox должен содержать ровно 4 значения: lon_min,lat_min,lon_max,lat_max",
        )
    try:
        lon_min, lat_min, lon_max, lat_max = (float(p.strip()) for p in parts)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Все значения bbox должны быть числами",
        )
    return lon_min, lat_min, lon_max, lat_max


def _row_to_risk(row) -> Optional[RiskScoreOut]:
    if row.get("final_score") is None:
        return None
    return RiskScoreOut(
        baseline_score=float(row["baseline_score"]) if row["baseline_score"] is not None else None,
        dynamic_modifier=float(row["dynamic_modifier"]) if row["dynamic_modifier"] is not None else None,
        final_score=float(row["final_score"]) if row["final_score"] is not None else None,
        score_date=str(row["score_date"]) if row["score_date"] is not None else None,
    )


def _call_claude_haiku(shap_factors: List[Dict[str, Any]]) -> str:
    """Generate a short Russian explanation of risk factors using Claude Haiku."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _mock_explanation(shap_factors)

    try:
        import anthropic  # noqa: PLC0415

        client = anthropic.Anthropic(api_key=api_key)
        factors_text = "\n".join(
            f"- {f['feature']}: влияние {f['shap_value']:+.4f} (значение: {f['value']})"
            for f in shap_factors
        )
        prompt = (
            "Ты эксперт по пожарной безопасности. "
            "Ниже представлены 5 ключевых факторов риска здания с их вкладом (SHAP-значение) "
            "в прогноз частоты пожаров:\n\n"
            f"{factors_text}\n\n"
            "Напиши краткое объяснение (2-3 предложения) на русском языке, "
            "почему данное здание имеет такой уровень риска. "
            "Не используй технические термины SHAP. "
            "Говори о реальных причинах пожарного риска."
        )
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        parts: List[str] = []
        for block in getattr(response, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip() or _mock_explanation(shap_factors)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude Haiku call failed: %s", exc)
        return _mock_explanation(shap_factors)


def _mock_explanation(shap_factors: List[Dict[str, Any]]) -> str:
    """Fallback Russian explanation without Claude."""
    if not shap_factors:
        return "Данные о факторах риска для этого здания недоступны."
    top = shap_factors[0]
    feature_ru = {
        "nearest_hydrant_m": "расстояние до ближайшего гидранта",
        "nearest_station_m": "расстояние до пожарной части",
        "incidents_500m_3y": "количество пожаров в радиусе 500 м за 3 года",
        "incidents_on_building_3y": "количество пожаров в здании за 3 года",
        "building_density_500m": "плотность застройки",
        "age_years": "возраст здания",
        "population_estimate": "оценочная численность жителей",
        "days_since_last_incident": "время с последнего пожара",
        "days_since_last_inspection": "время с последней проверки",
    }.get(top["feature"], top["feature"])
    return (
        f"Наибольшее влияние на уровень риска оказывает показатель «{feature_ru}». "
        "Рекомендуется провести внеплановую проверку объекта и устранить выявленные нарушения. "
        "Для снижения риска необходимо обеспечить своевременное техническое обслуживание систем пожаротушения."
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _risk_level(final_score: Optional[float]) -> str:
    if final_score is None:
        return "unknown"
    if final_score > 1.5:
        return "high"
    if final_score > 0.5:
        return "medium"
    return "low"


@router.get("/buildings")
async def list_buildings(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    bbox: Optional[str] = Query(
        None,
        description="lon_min,lat_min,lon_max,lat_max — ограничивает выдачу видимой областью карты",
    ),
    building_type: Optional[str] = Query(
        None, description="Фильтр по типу: residential | commercial | industrial | public | other"
    ),
    risk_level: Optional[str] = Query(
        None, description="Фильтр по уровню риска: high | medium | low | unknown"
    ),
    district: Optional[str] = Query(None, description="Фильтр по району"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Список зданий города с риск-баллом (JOIN с latest risk_scores).

    Возвращает форму-суперсет: подходит и `Building` (страница планов),
    и `BuildingRiskItem` (слой риска на карте).
    """

    sql = """
        WITH latest_risk AS (
            SELECT DISTINCT ON (building_id)
                   building_id, baseline_score, dynamic_modifier, final_score, score_date
            FROM risk_scores
            ORDER BY building_id, score_date DESC
        )
        SELECT b.id, b.city_id, b.address, b.name, b.district, b.object_type,
               b.floors_above, b.total_area_sqm,
               ST_Y(b.centroid) AS lat, ST_X(b.centroid) AS lon,
               b.details,
               r.baseline_score, r.dynamic_modifier, r.final_score, r.score_date
        FROM buildings b
        LEFT JOIN latest_risk r ON r.building_id = b.id
        WHERE b.city_id = :city
    """
    params: Dict[str, Any] = {"city": city, "limit": limit, "offset": offset}

    if bbox:
        lon_min, lat_min, lon_max, lat_max = _parse_bbox(bbox)
        sql += " AND ST_X(b.centroid) BETWEEN :lon_min AND :lon_max"
        sql += " AND ST_Y(b.centroid) BETWEEN :lat_min AND :lat_max"
        params.update({"lon_min": lon_min, "lon_max": lon_max, "lat_min": lat_min, "lat_max": lat_max})

    if building_type:
        sql += " AND b.object_type = :building_type"
        params["building_type"] = building_type

    if district:
        sql += " AND b.district = :district"
        params["district"] = district

    sql += " ORDER BY r.final_score DESC NULLS LAST, b.name NULLS LAST, b.id"
    sql += " LIMIT :limit OFFSET :offset"

    result = await session.execute(text(sql), params)
    rows = [dict(row) for row in result.mappings().all()]

    items: List[Dict[str, Any]] = []
    for row in rows:
        item = _row_to_frontend_building(row)
        final_score = float(row["final_score"]) if row.get("final_score") is not None else None
        level = _risk_level(final_score)
        if risk_level and level != risk_level:
            continue
        item["building_id"] = row["id"]
        item["building_type"] = row.get("object_type")
        item["final_score"] = final_score if final_score is not None else 0.0
        item["baseline_score"] = (
            float(row["baseline_score"]) if row.get("baseline_score") is not None else 0.0
        )
        item["dynamic_modifier"] = (
            float(row["dynamic_modifier"]) if row.get("dynamic_modifier") is not None else 1.0
        )
        item["risk_level"] = level
        items.append(item)
    return items


@router.get("/buildings/{building_id}")
async def get_building(
    building_id: str,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Детали здания по id (форма фронта, без auth — QR-сценарий)."""
    result = await session.execute(
        text(
            """
            SELECT id, city_id, address, name, district, object_type,
                   floors_above, total_area_sqm,
                   ST_Y(centroid) AS lat, ST_X(centroid) AS lon,
                   details
            FROM buildings
            WHERE id = :id
            """
        ),
        {"id": building_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Здание не найдено")
    return _row_to_frontend_building(dict(row))


VALID_HORIZONS = {7, 30, 90}


@router.get("/buildings/{building_id}/risk", response_model=RiskHorizonOut)
async def get_building_risk(
    building_id: str,
    horizon: int = Query(30, description="Горизонт прогноза в днях: 7, 30 или 90"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> RiskHorizonOut:
    """Return risk forecast for a building over the given horizon."""

    if horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=422,
            detail=f"Недопустимый горизонт: {horizon}. Допустимые значения: 7, 30, 90",
        )

    result = await session.execute(
        text(
            """
            SELECT baseline_score, dynamic_modifier, final_score
            FROM risk_scores
            WHERE building_id = :building_id
            ORDER BY score_date DESC
            LIMIT 1
            """
        ),
        {"building_id": building_id},
    )
    row = result.mappings().first()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Данные о риске для этого здания не найдены. Запустите compute_risk_scores.",
        )

    baseline_score = float(row["baseline_score"])
    dynamic_modifier = float(row["dynamic_modifier"]) if row["dynamic_modifier"] is not None else 1.0
    final_score = float(row["final_score"])
    expected_incidents = final_score * horizon / 365.0

    return RiskHorizonOut(
        baseline_score=baseline_score,
        dynamic_modifier=dynamic_modifier,
        final_score=final_score,
        horizon_days=horizon,
        expected_incidents=round(expected_incidents, 6),
    )


@router.get("/buildings/{building_id}/factors", response_model=FactorsOut)
async def get_building_factors(
    building_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> FactorsOut:
    """Return SHAP factors and a Claude Haiku Russian explanation (24h cache)."""

    now = time.time()
    cached = _FACTORS_CACHE.get(building_id)
    if cached and now - cached["ts"] < _FACTORS_TTL:
        return FactorsOut(**cached["data"])

    result = await session.execute(
        text(
            """
            SELECT shap_values
            FROM risk_scores
            WHERE building_id = :building_id
            ORDER BY score_date DESC
            LIMIT 1
            """
        ),
        {"building_id": building_id},
    )
    row = result.mappings().first()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Данные о риске для этого здания не найдены. Запустите compute_risk_scores.",
        )

    shap_raw = row["shap_values"]
    shap_factors: List[Dict[str, Any]] = []
    if shap_raw is not None:
        import json as _json  # noqa: PLC0415

        if isinstance(shap_raw, str):
            shap_factors = _json.loads(shap_raw)
        else:
            shap_factors = shap_raw

    explanation = _call_claude_haiku(shap_factors)

    data: Dict[str, Any] = {
        "shap_factors": shap_factors,
        "explanation": explanation,
    }
    _FACTORS_CACHE[building_id] = {"ts": now, "data": data}

    return FactorsOut(
        shap_factors=[ShapFactor(**f) for f in shap_factors],
        explanation=explanation,
    )
