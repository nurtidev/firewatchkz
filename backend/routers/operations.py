from fastapi import APIRouter
from fastapi import Query

from services.data_loader import data_loader

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("")
def list_operations(city: str = Query(...)) -> dict:
    operations = data_loader.get_operations(city).sort_values("date", ascending=False).copy()
    operations["date"] = operations["date"].dt.strftime("%Y-%m-%d")
    return {"total": int(len(operations)), "items": operations.to_dict(orient="records")}


@router.get("/kpi")
def get_operations_kpi(city: str = Query(...)) -> dict:
    operations = data_loader.get_operations(city)
    stations = data_loader.get_stations(city)

    station_lookup = {station["id"]: station["name"] for station in stations}

    avg_response_time = round(float(operations["response_time_min"].mean()), 1) if not operations.empty else 0.0
    operations_count = int(len(operations))

    station_times = (
        operations.groupby("station_id")["response_time_min"].mean().sort_values(ascending=True)
        if not operations.empty
        else None
    )
    fastest_station_id = station_times.index[0] if station_times is not None and not station_times.empty else None

    district_times = (
        operations.groupby("district")["response_time_min"].mean().sort_values(ascending=False)
        if not operations.empty
        else None
    )
    slowest_district = district_times.index[0] if district_times is not None and not district_times.empty else None

    return {
        "city": city.lower(),
        "avg_response_time_min": avg_response_time,
        "operations_count": operations_count,
        "fastest_station": station_lookup.get(fastest_station_id, fastest_station_id),
        "slowest_district": slowest_district,
    }
