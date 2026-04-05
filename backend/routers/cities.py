import json
from pathlib import Path

from fastapi import APIRouter
from fastapi import HTTPException
from services.data_loader import CITY_CONFIG, data_loader

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("")
def list_cities() -> list[dict]:
    return data_loader.get_cities()


@router.get("/{city_id}/geojson")
def get_city_geojson(city_id: str) -> dict:
    city_key = city_id.lower()
    if city_key not in CITY_CONFIG:
        raise HTTPException(status_code=404, detail="City not found")
    geojson_path = _PROJECT_ROOT / CITY_CONFIG[city_key]["geojson_path"]
    if not geojson_path.exists():
        raise HTTPException(status_code=404, detail="GeoJSON not found for this city")
    return json.loads(geojson_path.read_text(encoding="utf-8"))


@router.get("/{city_id}")
def get_city(city_id: str) -> dict:
    city_key = city_id.lower()
    if city_key not in CITY_CONFIG:
        raise HTTPException(status_code=404, detail="City not found")
    config = CITY_CONFIG[city_key]
    return {
        "id": config["id"],
        "name": config["name"],
        "center": config["center"],
        "zoom": config["zoom"],
    }
