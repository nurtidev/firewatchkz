from __future__ import annotations

import os
import re

try:
    import anthropic
except ImportError:  # pragma: no cover - dependency may be absent in local sandbox
    anthropic = None

from services.logger import log

MODEL_NAME = "claude-haiku-4-5"
# Haiku 4.5 pricing: $0.80/1M input tokens, $4.00/1M output tokens
_INPUT_COST_PER_TOKEN = 0.80 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 4.00 / 1_000_000
_TERM_REPLACEMENTS = {
    "electrical": "электрооборудование",
    "open_flame": "открытое пламя",
    "open flame": "открытое пламя",
    "risk_score": "индекс риска",
    "smoking": "неосторожное курение",
    "heating": "система отопления",
    "arson": "поджог",
    "other": "прочие причины",
    "residential": "жилой объект",
    "commercial": "коммерческий объект",
    "industrial": "производственный объект",
    "public": "общественный объект",
    "mixed_use": "многофункциональный объект",
}


class ClaudeClient:
    def __init__(self) -> None:
        self.api_key = ""
        self.client = None
        self._refresh_client()

    def chat(self, city_name: str, message: str, history: list[dict], context: str) -> str:
        self._refresh_client()
        if not self.client:
            return self._mock_reply(message, city_name)

        system_prompt = (
            "You are FireWatch AI Analyst — an expert in fire safety data analysis.\n"
            f"You have access to fire incident data for {city_name}.\n\n"
            f"{context}\n\n"
            "Answer in the same language as the user's latest message. "
            "Be concise, data-driven, and reference specific numbers from the data."
        )

        messages = self._normalize_history(history)
        messages.append({"role": "user", "content": message})
        try:
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=1000,
                system=system_prompt,
                messages=messages,
            )
            self._log_usage(response)
            return self._response_text(response).strip()
        except Exception:
            return self._mock_reply(message, city_name)

    def _log_usage(self, response: object) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cost_usd = round(
            input_tokens * _INPUT_COST_PER_TOKEN + output_tokens * _OUTPUT_COST_PER_TOKEN,
            6,
        )
        log.info(
            "claude_api_call",
            model=MODEL_NAME,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

    def _refresh_client(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if api_key == self.api_key and self.client is not None:
            return
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key) if api_key and anthropic else None

    def _normalize_history(self, history: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for item in history:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                normalized.append({"role": role, "content": content})
        return normalized

    def _response_text(self, response: object) -> str:
        parts: list[str] = []
        for block in getattr(response, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()

    def _localize_text(self, value: str) -> str:
        localized = value
        for source, target in _TERM_REPLACEMENTS.items():
            localized = re.sub(rf"\b{re.escape(source)}\b", target, localized, flags=re.IGNORECASE)
        localized = re.sub(r"\s{2,}", " ", localized)
        return localized.strip()

    def _mock_reply(self, message: str, city_name: str) -> str:
        if re.search(r"[А-Яа-яӘәҒғҚқҢңӨөҰұҮүІі]", message):
            return (
                f"По данным FireWatch для города {city_name} сейчас стоит смотреть на районы с самым высоким риском, "
                "электрические причины и накопленный материальный ущерб. После подключения Anthropic API я смогу дать "
                "более точный аналитический ответ с опорой на контекст запроса."
            )
        return (
            f"For {city_name}, the current priority is to focus on the highest-risk districts, electrical causes, "
            "and high-damage incident clusters. Once the Anthropic API key is configured, I can provide a more "
            "specific data-grounded answer."
        )


claude_client = ClaudeClient()
