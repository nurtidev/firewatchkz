from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

from services.data_loader import data_loader

router = APIRouter(prefix="/inspector", tags=["inspector"])

PEAK_MONTHS = {1, 2, 5, 6}

CAUSE_RU = {
    "electrical": "электропроводка",
    "open_flame": "открытый огонь",
    "arson": "поджог",
    "children": "детская шалость",
    "other": "прочее",
}

BUILDING_RU = {
    "residential": "жилой",
    "commercial": "коммерческий",
    "industrial": "промышленный",
    "construction": "стройплощадка",
    "other": "прочее",
}

PRIORITY_THRESHOLDS = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _priority(matched: int) -> str:
    if matched >= 4:
        return "critical"
    if matched >= 3:
        return "high"
    if matched >= 2:
        return "medium"
    return "low"


def _days_since_last(incidents: pd.DataFrame, district: str) -> Optional[int]:
    district_incidents = incidents[incidents["district"] == district]
    if district_incidents.empty:
        return None
    last = district_incidents["date"].max()
    return (pd.Timestamp.now().normalize() - last).days


def _trending_cause(incidents: pd.DataFrame, district: str, days: int = 30) -> Optional[str]:
    cutoff = pd.Timestamp.now().normalize() - timedelta(days=days)
    recent = incidents[(incidents["district"] == district) & (incidents["date"] >= cutoff)]
    if recent.empty:
        return None
    return str(recent["cause"].value_counts().index[0])


@router.get("")
def get_inspector(city: str = Query(...)) -> list[dict]:
    incidents = data_loader.get_incidents(city)
    district_stats = data_loader.get_district_stats(city)

    now = pd.Timestamp.now().normalize()
    current_month = now.month
    is_peak_month = current_month in PEAK_MONTHS

    results: list[dict] = []

    for _, row in district_stats.iterrows():
        district = str(row["district"])
        risk_score = float(row["risk_score"])
        total_incidents = int(row["total_incidents"])
        avg_damage = int(row["avg_damage_tenge"])

        factors: list[dict] = []
        matched = 0

        # Factor 1: high risk score
        if risk_score >= 70:
            factors.append({
                "matched": True,
                "label": f"Высокий индекс риска района: {risk_score:.0f}/100",
            })
            matched += 1
        else:
            factors.append({
                "matched": False,
                "label": f"Индекс риска района: {risk_score:.0f}/100",
            })

        # Factor 2: recent incident (last 14 days)
        days_since = _days_since_last(incidents, district)
        if days_since is not None and days_since <= 14:
            factors.append({
                "matched": True,
                "label": f"Последний пожар {days_since} дн. назад — повышен риск повтора",
            })
            matched += 1
        else:
            label = f"Последний пожар {days_since} дн. назад" if days_since else "Нет данных об инцидентах"
            factors.append({"matched": False, "label": label})

        # Factor 3: peak season
        month_name = calendar.month_name[current_month]
        if is_peak_month:
            factors.append({
                "matched": True,
                "label": f"Сезонный пик — {month_name} исторически опасный месяц",
            })
            matched += 1
        else:
            factors.append({
                "matched": False,
                "label": f"Вне сезонного пика ({month_name})",
            })

        # Factor 4: dangerous building types dominate
        district_incidents = incidents[incidents["district"] == district]
        dangerous_share = 0.0
        top_building = None
        if not district_incidents.empty:
            bt_counts = district_incidents["building_type"].value_counts()
            top_building = str(bt_counts.index[0])
            dangerous = district_incidents[
                district_incidents["building_type"].isin(["industrial", "construction"])
            ]
            dangerous_share = len(dangerous) / len(district_incidents)

        if dangerous_share >= 0.25:
            pct = int(dangerous_share * 100)
            factors.append({
                "matched": True,
                "label": f"{pct}% инцидентов — промышленные объекты и стройплощадки",
            })
            matched += 1
        else:
            bt_label = BUILDING_RU.get(top_building or "", top_building or "—")
            factors.append({
                "matched": False,
                "label": f"Преобладающий тип: {bt_label}",
            })

        # Factor 5: trending cause last 30 days
        trending = _trending_cause(incidents, district, days=30)
        trending_ru = CAUSE_RU.get(trending or "", trending or "—")
        if trending in ("electrical", "arson"):
            factors.append({
                "matched": True,
                "label": f"Топ причина последних 30 дней: {trending_ru}",
            })
            matched += 1
        else:
            factors.append({
                "matched": False,
                "label": f"Топ причина последних 30 дней: {trending_ru}",
            })

        priority = _priority(matched)

        results.append({
            "district": district,
            "priority": priority,
            "matched_factors": matched,
            "total_factors": len(factors),
            "risk_score": risk_score,
            "days_since_last_incident": days_since,
            "avg_damage_tenge": avg_damage,
            "recommendation": _recommendation(priority, district, trending_ru),
            "factors": factors,
        })

    results.sort(key=lambda x: (-x["matched_factors"], -x["risk_score"]))
    return results


def _recommendation(priority: str, district: str, top_cause: str) -> str:
    if priority == "critical":
        return (
            f"Немедленная внеплановая проверка объектов в районе {district}. "
            f"Особое внимание: {top_cause}. Рекомендуется выезд в течение 24 часов."
        )
    if priority == "high":
        return (
            f"Плановая проверка в районе {district} в ближайшие 3 дня. "
            f"Приоритет: объекты с рисками по причине «{top_cause}»."
        )
    if priority == "medium":
        return (
            f"Включить {district} в план проверок на текущей неделе. "
            f"Мониторинг ситуации с причиной «{top_cause}»."
        )
    return f"Стандартный плановый мониторинг района {district}."
