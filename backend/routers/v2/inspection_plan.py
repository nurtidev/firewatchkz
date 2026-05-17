"""
routers/v2/inspection_plan.py — Inspection plan endpoint (API v2).

GET /api/v2/inspection-plan?city=astana
Auth: require_inspector_or_above
Returns: {city, generated_at, items: [{district, priority, reason, recommended_actions}]}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_inspector_or_above
from services.data_loader_v2 import DataLoaderV2

router = APIRouter()

# Mirrors v1 inspection_planner.CAUSE_ACTIONS
_CAUSE_ACTIONS: Dict[str, str] = {
    "electrical": "Check electrical systems",
    "open_flame": "Inspect open flame safety controls",
    "arson": "Coordinate targeted patrols and site security checks",
    "children": "Run residential prevention outreach for families and schools",
    "other": "Review district-specific prevention protocols",
}


def _priority(risk_score: float) -> str:
    if risk_score >= 70:
        return "high"
    if risk_score >= 40:
        return "medium"
    return "low"


def _reason(risk_score: float, top_cause: str) -> str:
    cause_label = top_cause.replace("_", " ")
    if risk_score >= 70:
        return f"High risk score and repeated {cause_label} incident pattern"
    if risk_score >= 40:
        return f"Elevated district risk with notable {cause_label} incidents"
    return f"Baseline monitoring area with lower but persistent {cause_label} incidents"


def _actions(top_cause: str) -> List[str]:
    return [
        "Inspect priority facilities in the district",
        _CAUSE_ACTIONS.get(top_cause, _CAUSE_ACTIONS["other"]),
        "Review hydrant availability",
    ]


@router.get("/inspection-plan", tags=["inspection-plan-v2"])
async def get_inspection_plan(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> Dict[str, Any]:
    """Generate a prioritised inspection plan for all districts in the city."""
    loader = DataLoaderV2()
    district_stats = await loader.get_district_stats(city)

    # Sort by risk_score DESC, then total_incidents DESC (mirrors v1 planner logic)
    sorted_stats = sorted(
        district_stats,
        key=lambda r: (
            float(r.get("risk_score") or 0),
            int(r.get("total_incidents") or 0),
        ),
        reverse=True,
    )

    items: List[Dict[str, Any]] = []
    for row in sorted_stats:
        district = str(row.get("district", ""))
        risk_score = float(row.get("risk_score") or 0)
        top_cause = str(row.get("top_cause") or "other")
        items.append(
            {
                "district": district,
                "priority": _priority(risk_score),
                "reason": _reason(risk_score, top_cause),
                "recommended_actions": _actions(top_cause),
            }
        )

    generated_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return {
        "city": city.lower(),
        "generated_at": generated_at,
        "items": items[: max(3, len(items))],
    }
