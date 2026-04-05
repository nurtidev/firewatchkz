from fastapi import APIRouter
from fastapi import Query

from services.data_loader import data_loader

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.get("")
def list_buildings(city: str = Query(...)) -> list[dict]:
    return data_loader.get_buildings(city)
