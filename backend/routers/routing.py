from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.data_loader import data_loader
from services.emergency_router import estimate_route

router = APIRouter(prefix="/routing", tags=["routing"])


class RouteRequest(BaseModel):
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    city: str = "astana"
    station_id: Optional[str] = None


@router.post("/estimate")
def estimate_emergency_route(body: RouteRequest) -> dict:
    """
    Рассчитывает время прибытия для обычного и экстренного режима.
    Экстренный режим: выделенные полосы, встречное движение на односторонних улицах.
    """
    try:
        result = estimate_route(
            from_lat=body.from_lat,
            from_lon=body.from_lon,
            to_lat=body.to_lat,
            to_lon=body.to_lon,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка маршрутизации: {exc}") from exc

    result["city"] = body.city
    if body.station_id:
        result["station_id"] = body.station_id
    return result


@router.get("/stations")
def list_routing_stations(city: str = Query(...)) -> list[dict]:
    """Список пожарных частей с координатами для выбора точки отправления."""
    stations = data_loader.get_stations(city)
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "district": s["district"],
            "lat": s["lat"],
            "lon": s["lon"],
        }
        for s in stations
    ]
