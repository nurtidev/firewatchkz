from typing import Optional

from fastapi import APIRouter
from fastapi import Query
from services.data_loader import data_loader

router = APIRouter(tags=["incidents"])


@router.get("/incidents")
def list_incidents(
    city: str = Query(...),
    district: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    incidents = data_loader.get_incidents(city=city, district=district).sort_values("date", ascending=False)
    total = int(len(incidents))
    items = incidents.head(limit).copy()
    items["date"] = items["date"].dt.strftime("%Y-%m-%d")
    return {"total": total, "items": items.to_dict(orient="records")}


@router.get("/risk-map")
def get_risk_map(city: str = Query(...)) -> list[dict]:
    incidents = data_loader.get_incidents(city)
    district_stats = data_loader.get_district_stats(city)

    cause_summary = (
        incidents.groupby(["district", "cause"])
        .size()
        .reset_index(name="count")
        .sort_values(["district", "count", "cause"], ascending=[True, False, True])
        .drop_duplicates(subset=["district"])
        .rename(columns={"cause": "top_cause"})
    )
    building_summary = (
        incidents.groupby(["district", "building_type"])
        .size()
        .reset_index(name="count")
        .sort_values(["district", "count", "building_type"], ascending=[True, False, True])
        .drop_duplicates(subset=["district"])
        .rename(columns={"building_type": "top_building_type"})
    )

    risk_map = (
        district_stats.merge(cause_summary[["district", "top_cause"]], on="district", how="left")
        .merge(building_summary[["district", "top_building_type"]], on="district", how="left")
        .sort_values("risk_score", ascending=False)
        .reset_index(drop=True)
    )
    risk_map["risk_score"] = risk_map["risk_score"].round(2)
    risk_map["avg_damage_tenge"] = risk_map["avg_damage_tenge"].astype(int)
    risk_map["total_incidents"] = risk_map["total_incidents"].astype(int)
    return risk_map.to_dict(orient="records")
