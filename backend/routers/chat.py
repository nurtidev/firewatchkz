from pydantic import BaseModel, Field

from fastapi import APIRouter
from services.claude_client import claude_client
from services.data_loader import CITY_CONFIG, data_loader
from routers.kpi import get_kpi

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    city: str
    history: list[ChatMessage] = Field(default_factory=list)


@router.post("")
def chat_with_ai(payload: ChatRequest) -> dict[str, str]:
    city_key = payload.city.lower()
    district_stats = data_loader.get_district_stats(city_key)
    kpi_summary = get_kpi(city_key)
    context = (
        "Summary statistics:\n"
        f"{kpi_summary}\n\n"
        "District risk scores:\n"
        f"{district_stats.to_string(index=False)}"
    )
    reply = claude_client.chat(
        city_name=CITY_CONFIG[city_key]["name"],
        message=payload.message,
        history=[item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in payload.history],
        context=context,
    )
    return {"reply": reply}
