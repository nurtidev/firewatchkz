"""
routers/v2/telegram.py — Telegram notification endpoints (API v2).

POST /api/v2/telegram/test?city=astana
GET  /api/v2/telegram/config
Auth: none (same as v1)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.data_loader_v2 import DataLoaderV2

router = APIRouter()

# Lazy import — telegram library may not be installed
try:
    from telegram import Bot as _TelegramBot  # type: ignore
except ImportError:
    _TelegramBot = None


def _is_configured() -> bool:
    """Return True if both Telegram env vars are set and the library is available."""
    return bool(
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        and os.getenv("TELEGRAM_CHAT_ID", "").strip()
        and _TelegramBot is not None
    )


async def _build_message(city: str, district_stats: List[Dict[str, Any]]) -> str:
    """Build the HTML alert message from district stats."""
    _CITY_NAMES: Dict[str, str] = {
        "astana": "Астана",
        "almaty": "Алматы",
        "shymkent": "Шымкент",
    }
    city_name = _CITY_NAMES.get(city.lower(), city.capitalize())

    # Sort by risk_score descending, take top 3
    sorted_stats = sorted(
        district_stats,
        key=lambda r: float(r.get("risk_score") or 0),
        reverse=True,
    )
    top3 = sorted_stats[:3]

    lines: List[str] = [f"🔥 <b>FireWatch — {city_name}</b>", ""]
    lines.append("⚠️ <b>Районы высокого риска на сегодня:</b>")

    for row in top3:
        risk_score = float(row.get("risk_score") or 0)
        bar_filled = int(risk_score / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        avg_damage = int(row.get("avg_damage") or 0)
        avg_damage_fmt = f"{avg_damage:,}".replace(",", " ")
        lines.append(
            f"  • <b>{row['district']}</b> — риск {risk_score:.0f}/100\n"
            f"    {bar}\n"
            f"    Инцидентов (12 мес): {row.get('incidents_last_12m', 0)}  |  "
            f"Ср. ущерб: {avg_damage_fmt} ₸"
        )

    highest = top3[0]["district"] if top3 else "—"
    lines += [
        "",
        f"🏆 Самый опасный район: <b>{highest}</b>",
        "📋 Рекомендуется: провести профилактическую инспекцию",
        "",
        "<i>FireWatch · Ежедневный дайджест</i>",
    ]
    return "\n".join(lines)


@router.post("/telegram/test", tags=["telegram-v2"])
async def send_test_alert(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Send a test Telegram alert with current district risk data."""
    if not _is_configured():
        return {"status": "not configured"}

    loader = DataLoaderV2()
    district_stats = await loader.get_district_stats(city)

    message = await _build_message(city, district_stats)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    bot = _TelegramBot(token=bot_token)
    sent = await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
    return {"status": "sent", "message_id": sent.message_id}


@router.get("/telegram/config", tags=["telegram-v2"])
def get_telegram_config() -> Dict[str, Any]:
    """Return masked Telegram configuration status."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    masked_token = ""
    if bot_token:
        masked_token = (
            f"{bot_token[:4]}***{bot_token[-4:]}"
            if len(bot_token) >= 8
            else "***"
        )

    return {
        "status": "configured" if _is_configured() else "not configured",
        "bot_token_masked": masked_token,
        "chat_id": chat_id if chat_id else None,
    }
