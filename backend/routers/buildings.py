from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from services.data_loader import data_loader, CITY_CONFIG

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.get("")
def list_buildings(city: str = Query(...)) -> list[dict]:
    return data_loader.get_buildings(city)


@router.get("/{building_id}")
def get_building(building_id: str, city: Optional[str] = Query(None)) -> dict:
    """
    Публичный endpoint для просмотра оперативного плана здания.
    Используется при сканировании QR-кода — авторизация не требуется.
    city опционален: если не указан, ищем по всем городам.
    """
    if city:
        building = data_loader.get_building_by_id(city, building_id)
    else:
        building = None
        for city_key in CITY_CONFIG:
            found = data_loader.get_building_by_id(city_key, building_id)
            if found:
                building = found
                break

    if not building:
        raise HTTPException(status_code=404, detail="Здание не найдено")
    return building
