import math

from fastapi import APIRouter
from fastapi import Query

from services.data_loader import data_loader

router = APIRouter(prefix="/stations", tags=["stations"])


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


@router.get("")
def list_stations(city: str = Query(...)) -> list[dict]:
    return data_loader.get_stations(city)


@router.get("/coverage")
def get_station_coverage(city: str = Query(...)) -> list[dict]:
    stations = data_loader.get_stations(city)
    district_centroids = data_loader.get_district_centroids(city)
    coverage: list[dict] = []

    for district, (center_lat, center_lon) in district_centroids.items():
        nearest_station = min(
            stations,
            key=lambda station: _distance_km(center_lat, center_lon, station["lat"], station["lon"]),
        )
        distance_km = _distance_km(
            center_lat,
            center_lon,
            nearest_station["lat"],
            nearest_station["lon"],
        )
        coverage.append(
            {
                "district": district,
                "nearest_station": nearest_station["name"],
                "distance_km": round(distance_km, 2),
                "estimated_response_min": round(max(3, distance_km * 2.5), 1),
            }
        )

    return sorted(coverage, key=lambda item: item["district"])
