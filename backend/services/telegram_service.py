from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    from telegram import Bot
except ImportError:  # pragma: no cover - dependency may be absent in local sandbox
    Bot = None

_CITY_NAMES: Dict[str, str] = {"astana": "Астана", "almaty": "Алматы"}


class TelegramService:
    def __init__(self) -> None:
        self.bot_token = ""
        self.chat_id = ""
        self._refresh_config()

    def is_configured(self) -> bool:
        self._refresh_config()
        return bool(self.bot_token and self.chat_id and Bot)

    async def send_test_alert(self, city: str, district_rows: List[Dict[str, Any]] = None) -> dict[str, Any]:
        self._refresh_config()
        if not self.is_configured():
            return {"status": "not configured"}

        city_name = _CITY_NAMES.get(city.lower(), city)
        rows = sorted(district_rows or [], key=lambda r: r.get("risk_score", 0), reverse=True)[:3]

        lines = [f"🔥 <b>FireWatch — {city_name}</b>", ""]
        lines.append("⚠️ <b>Районы высокого риска на сегодня:</b>")
        for row in rows:
            score = row.get("risk_score", 0)
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            lines.append(
                f"  • <b>{row['district']}</b> — риск {score:.0f}/100\n"
                f"    {bar}\n"
                f"    Инцидентов (12 мес): {row.get('total_incidents', 0)}  |  "
                f"Ср. ущерб: {int(row.get('avg_damage_tenge', 0)):,} ₸".replace(",", " ")
            )

        highest = rows[0]["district"] if rows else "—"
        lines += [
            "",
            f"🏆 Самый опасный район: <b>{highest}</b>",
            "📋 Рекомендуется: провести профилактическую инспекцию",
            "",
            "<i>FireWatch · Ежедневный дайджест</i>",
        ]
        message = "\n".join(lines)

        bot = Bot(token=self.bot_token)
        sent = await bot.send_message(chat_id=self.chat_id, text=message, parse_mode="HTML")
        return {"status": "sent", "message_id": sent.message_id}

    def get_config(self) -> dict[str, Any]:
        self._refresh_config()
        masked_token = ""
        if self.bot_token:
            masked_token = f"{self.bot_token[:4]}***{self.bot_token[-4:]}" if len(self.bot_token) >= 8 else "***"
        return {
            "status": "configured" if self.is_configured() else "not configured",
            "bot_token_masked": masked_token,
            "chat_id": self.chat_id if self.chat_id else None,
        }

    def _refresh_config(self) -> None:
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()


telegram_service = TelegramService()
