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

    def get_recommendations(
        self,
        city: str,
        city_name: str,
        district_stats_table: str,
        top_causes: str,
        buildings: list[dict],
    ) -> list[dict]:
        self._refresh_client()
        cached_entry = _RECOMMENDATION_CACHE.get(city)
        now = datetime.utcnow()
        if cached_entry and now - cached_entry["timestamp"] < _CACHE_TTL:
            return self._localize_payload(cached_entry["payload"])

        if not self.client:
            payload = self._localize_payload(self._mock_recommendations(city_name, buildings))
            _RECOMMENDATION_CACHE[city] = {"timestamp": now, "payload": payload}
            return payload

        buildings_table = self._buildings_context(buildings)
        system_prompt = (
            "Ты эксперт по пожарной безопасности для городского департамента.\n"
            f"Город: {city_name}\n"
            "Ниже данные по рискам районов:\n"
            f"{self._localize_text(district_stats_table)}\n\n"
            f"Топ причин пожаров: {self._localize_text(top_causes)}\n\n"
            "Ниже приоритетные объекты и здания для инспекции:\n"
            f"{buildings_table}\n\n"
            "Сгенерируй ровно 5 конкретных рекомендаций.\n"
            "Пиши только на русском языке.\n"
            "Каждая рекомендация должна ссылаться на конкретное здание, объект или тип здания.\n"
            "Не используй английские слова и технические метки из сырых данных.\n"
            "Нельзя писать общие программы уровня 'launch initiative' или 'establish center'.\n"
            "Формулируй рекомендации как действия для инспектора или департамента.\n"
            'Верни ТОЛЬКО JSON-массив объектов формата:\n'
            '[{"priority":"high|medium|low","title":"...","description":"...","expected_impact":"..."}]'
        )

        try:
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": "Сформируй рекомендации сейчас."}],
            )
            text = self._response_text(response)
            payload = self._localize_payload(self._parse_recommendations(text))
        except Exception:
            payload = self._localize_payload(self._mock_recommendations(city_name, buildings))
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
                    "title": self._localize_text(item.get("title", "")),
                    "description": self._localize_text(item.get("description", "")),
                    "expected_impact": self._localize_text(item.get("expected_impact", "")),
                }
            )
        while len(recommendations) < 5:
            recommendations.append(self._mock_recommendations("Астана", [])[len(recommendations)])
        return recommendations

    def _mock_recommendations(self, city_name: str, buildings: list[dict]) -> list[dict]:
        primary = buildings[0] if len(buildings) > 0 else {"name": "главные жилые комплексы города", "district": city_name}
        secondary = buildings[1] if len(buildings) > 1 else primary
        tertiary = buildings[2] if len(buildings) > 2 else secondary
        return [
            {
                "priority": "high",
                "title": f"Проверить электроснабжение на объекте «{primary['name']}»",
                "description": f"Проведите внеплановую инспекцию электрощитовых, кабельных трасс и узлов нагрузки на объекте «{primary['name']}»{self._district_suffix(primary)}.",
                "expected_impact": "Снижение вероятности возгораний по электрическим причинам в ближайшие 1-2 месяца.",
            },
            {
                "priority": "high",
                "title": f"Проверить пути эвакуации и противодымную защиту на объекте «{secondary['name']}»",
                "description": f"Сделайте адресную проверку лестничных клеток, систем дымоудаления и сценариев эвакуации на объекте «{secondary['name']}».",
                "expected_impact": "Снижение риска тяжелых последствий при пожаре в высотном или сложном объекте.",
            },
            {
                "priority": "medium",
                "title": f"Проверить внутреннее противопожарное водоснабжение на объекте «{tertiary['name']}»",
                "description": f"Проверьте доступность пожарных кранов, состояние насосного оборудования и оперативный доступ к воде на объекте «{tertiary['name']}».",
                "expected_impact": "Сокращение времени локализации пожара и уменьшение материального ущерба.",
            },
            {
                "priority": "medium",
                "title": "Проверить здания с высокой этажностью в районах повышенного риска",
                "description": "Сформируйте адресный список высотных жилых и смешанных объектов и проведите инспекции по чек-листу: электрика, эвакуация, дымоудаление, доступ пожарной техники.",
                "expected_impact": "Снижение сезонного риска на самых уязвимых объектах жилого фонда.",
            },
            {
                "priority": "low",
                "title": "Обновить карточки объектов для инспекторов на русском языке",
                "description": "Добавьте в карточки объектов адрес, район, этажность, время прибытия ПЧ, потенциальные опасности и приоритетный сценарий проверки для каждого здания.",
                "expected_impact": "Более быстрые и точные выездные проверки без потери контекста по объекту.",
            },
        ]

    def _localize_payload(self, payload: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for item in payload:
            normalized.append(
                {
                    "priority": item.get("priority", "medium"),
                    "title": self._localize_text(item.get("title", "")),
                    "description": self._localize_text(item.get("description", "")),
                    "expected_impact": self._localize_text(item.get("expected_impact", "")),
                }
            )
        return normalized

    def _buildings_context(self, buildings: list[dict]) -> str:
        if not buildings:
            return "Нет данных по зданиям."
        lines = []
        for building in buildings[:5]:
            lines.append(
                " | ".join(
                    [
                        f"Объект: {building.get('name')}",
                        f"Район: {building.get('district') or 'не указан'}",
                        f"Тип: {self._localize_text(building.get('object_type') or 'не указан')}",
                        f"Этажность: {building.get('floors_count') or 'не указана'}",
                        f"Время прибытия ПЧ: {building.get('arrival_time_minutes') or 'не указано'} мин",
                        f"Опасности: {self._localize_text(building.get('potential_hazards') or 'не указаны')}",
                    ]
                )
            )
        return "\n".join(lines)

    def _district_suffix(self, building: dict) -> str:
        district = building.get("district")
        if not district:
            return ""
        return f" в районе {district}"

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
