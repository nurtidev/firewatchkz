from fastapi import APIRouter
from fastapi import Query
from services.claude_client import claude_client
from services.data_loader import CITY_CONFIG, data_loader

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
def get_recommendations(city: str = Query(...)) -> list[dict]:
    city_key = city.lower()
    district_stats = data_loader.get_district_stats(city_key)
    incidents = data_loader.get_incidents(city_key)
    buildings = data_loader.get_buildings(city_key)
    top_causes = (
        incidents["cause"].value_counts().head(3).index.tolist()
        if not incidents.empty
        else []
    )
    district_stats_table = district_stats.to_string(index=False)
    city_name = CITY_CONFIG[city_key]["name"]
    prioritized_buildings = buildings[:5]
    return claude_client.get_recommendations(
        city=city_key,
        city_name=city_name,
        district_stats_table=district_stats_table,
        top_causes=", ".join(top_causes),
        buildings=prioritized_buildings,
    )
