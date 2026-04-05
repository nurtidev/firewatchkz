from __future__ import annotations

import os
from typing import Any

try:
    from telegram import Bot
except ImportError:  # pragma: no cover - dependency may be absent in local sandbox
    Bot = None

from services.data_loader import CITY_CONFIG, data_loader


class TelegramService:
    def __init__(self) -> None:
        self.bot_token = ""
        self.chat_id = ""
        self._refresh_config()

    def is_configured(self) -> bool:
        self._refresh_config()
        return bool(self.bot_token and self.chat_id and Bot)

    async def send_test_alert(self, city: str) -> dict[str, Any]:
        self._refresh_config()
        if not self.is_configured():
            return {"status": "not configured"}

        city_config = CITY_CONFIG.get(city.lower())
        district_stats = data_loader.get_district_stats(city)
        highest_risk = district_stats.sort_values("risk_score", ascending=False).iloc[0]
        message = (
            f"🔥 FireWatch Alert — {city_config['name']}\n"
            "Severity: HIGH\n"
            f"District: {highest_risk['district']}\n"
            f"Risk score: {highest_risk['risk_score']}/100\n"
            "Recommended: preventive inspection"
        )

        bot = Bot(token=self.bot_token)
        sent = await bot.send_message(chat_id=self.chat_id, text=message)
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
