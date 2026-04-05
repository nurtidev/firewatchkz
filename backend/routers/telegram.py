from fastapi import APIRouter
from fastapi import Query
from services.telegram_service import telegram_service

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/test")
async def send_test_alert(city: str = Query(...)) -> dict:
    return await telegram_service.send_test_alert(city)


@router.get("/config")
def get_telegram_config() -> dict:
    return telegram_service.get_config()
