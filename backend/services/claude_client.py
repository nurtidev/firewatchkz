from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

try:
    import anthropic
except ImportError:  # pragma: no cover - dependency may be absent in local sandbox
    anthropic = None


MODEL_NAME = "claude-haiku-4-5"
_RECOMMENDATION_CACHE: dict[str, dict] = {}
_CACHE_TTL = timedelta(hours=1)


class ClaudeClient:
    def __init__(self) -> None:
        self.api_key = ""
        self.client = None
        self._refresh_client()

    def get_recommendations(self, city: str, city_name: str, district_stats_table: str, top_causes: str) -> list[dict]:
        self._refresh_client()
        cached_entry = _RECOMMENDATION_CACHE.get(city)
        now = datetime.utcnow()
        if cached_entry and now - cached_entry["timestamp"] < _CACHE_TTL:
            return cached_entry["payload"]

        if not self.client:
            payload = self._mock_recommendations(city_name)
            _RECOMMENDATION_CACHE[city] = {"timestamp": now, "payload": payload}
            return payload

        system_prompt = (
            "You are a fire safety expert advising the fire department.\n"
            f"City: {city_name}\n"
            "District risk data:\n"
            f"{district_stats_table}\n"
            f"Top causes: {top_causes}\n"
            "Generate exactly 5 fire prevention recommendations.\n"
            'Return ONLY a JSON array of objects:\n'
            '[{"priority":"high|medium|low","title":"...","description":"...","expected_impact":"..."}]'
        )

        try:
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": "Provide the recommendations now."}],
            )
            text = self._response_text(response)
            payload = self._parse_recommendations(text)
        except Exception:
            payload = self._mock_recommendations(city_name)
        _RECOMMENDATION_CACHE[city] = {"timestamp": now, "payload": payload}
        return payload

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
            return self._response_text(response).strip()
        except Exception:
            return self._mock_reply(message, city_name)

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

    def _parse_recommendations(self, text: str) -> list[dict]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        payload = json.loads(cleaned)
        if not isinstance(payload, list):
            raise ValueError("Recommendations response is not a list")

        recommendations: list[dict] = []
        for item in payload[:5]:
            recommendations.append(
                {
                    "priority": item.get("priority", "medium"),
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "expected_impact": item.get("expected_impact", ""),
                }
            )
        while len(recommendations) < 5:
            recommendations.append(self._mock_recommendations("Астана")[len(recommendations)])
        return recommendations

    def _mock_recommendations(self, city_name: str) -> list[dict]:
        return [
            {
                "priority": "high",
                "title": f"Проверить электрощитовые в районе высокого риска ({city_name})",
                "description": "Проведите внеплановые inspections зданий с высокой долей electrical incidents.",
                "expected_impact": "Снижение числа возгораний по электрическим причинам в ближайшие 1-2 месяца.",
            },
            {
                "priority": "high",
                "title": "Запустить адресные профилактические обходы",
                "description": "Сфокусируйте обходы на районах с максимальным risk_score и повторяющимися инцидентами.",
                "expected_impact": "Быстрое снижение повторных бытовых и коммерческих возгораний.",
            },
            {
                "priority": "medium",
                "title": "Усилить контроль строительных площадок",
                "description": "Проверьте временную проводку, огневые работы и наличие первичных средств тушения.",
                "expected_impact": "Снижение ущерба на объектах construction и сокращение high-severity incidents.",
            },
            {
                "priority": "medium",
                "title": "Провести сезонную информационную кампанию",
                "description": "Напомните жителям и бизнесу о безопасной эксплуатации отопления и электросетей.",
                "expected_impact": "Сокращение сезонного пика инцидентов в ближайший период.",
            },
            {
                "priority": "low",
                "title": "Обновить районные чек-листы для инспекторов",
                "description": "Добавьте в чек-листы типовые причины инцидентов и фокус по конкретным building types.",
                "expected_impact": "Более точные профилактические действия и лучшее качество полевых проверок.",
            },
        ]

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
