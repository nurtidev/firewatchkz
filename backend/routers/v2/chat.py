"""
routers/v2/chat.py — Chat endpoint (API v2).

POST /api/v2/chat
Body: {message: str, city: str, history: list}
Auth: none (same as v1)
Returns: {reply: str}
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.claude_client import ClaudeClient
from services.data_loader_v2 import DataLoaderV2

router = APIRouter()

# City display names (mirrors v1 CITY_CONFIG)
_CITY_NAMES: Dict[str, str] = {
    "astana": "Астана",
    "almaty": "Алматы",
    "shymkent": "Шымкент",
}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    city: str
    history: List[ChatMessage] = Field(default_factory=list)


@router.post("/chat", tags=["chat-v2"])
async def chat_with_ai(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Chat with FireWatch AI analyst using live data context."""
    city_key = payload.city.lower()
    loader = DataLoaderV2()

    district_stats = await loader.get_district_stats(city_key)
    kpi = await loader.get_kpi(city_key)

    # Build context string matching v1 format
    kpi_summary = (
        f"total_incidents_ytd: {kpi.get('total_incidents_ytd')}, "
        f"vs_last_year_pct: {kpi.get('vs_last_year_pct')}%, "
        f"total_damage_tenge: {kpi.get('total_damage_tenge')}, "
        f"highest_risk_district: {kpi.get('highest_risk_district')}, "
        f"top_cause: {kpi.get('top_cause')}"
    )

    if district_stats:
        header = "  ".join(str(k) for k in district_stats[0].keys())
        rows_str = [header]
        for row in district_stats:
            rows_str.append("  ".join(str(v) for v in row.values()))
        district_stats_str = "\n".join(rows_str)
    else:
        district_stats_str = "Нет данных по районам"

    context = (
        "Summary statistics:\n"
        f"{kpi_summary}\n\n"
        "District risk scores:\n"
        f"{district_stats_str}"
    )

    city_name = _CITY_NAMES.get(city_key, city_key.capitalize())
    history = [
        item.model_dump() if hasattr(item, "model_dump") else item.dict()
        for item in payload.history
    ]

    client = ClaudeClient()
    reply = client.chat(
        city_name=city_name,
        message=payload.message,
        history=history,
        context=context,
    )
    return {"reply": reply}
