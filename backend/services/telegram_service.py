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
        top3 = district_stats.sort_values("risk_score", ascending=False).head(3)
        highest_risk = top3.iloc[0]

        lines = [f"🔥 <b>FireWatch — {city_config['name']}</b>", ""]
        lines.append("⚠️ <b>Районы высокого риска на сегодня:</b>")
        for _, row in top3.iterrows():
            bar = "█" * int(row["risk_score"] / 10) + "░" * (10 - int(row["risk_score"] / 10))
            lines.append(
                f"  • <b>{row['district']}</b> — риск {row['risk_score']:.0f}/100\n"
                f"    {bar}\n"
                f"    Инцидентов (12 мес): {row['total_incidents']}  |  "
                f"Ср. ущерб: {int(row['avg_damage_tenge']):,} ₸".replace(",", " ")
            )

        lines += [
            "",
            f"🏆 Самый опасный район: <b>{highest_risk['district']}</b>",
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
