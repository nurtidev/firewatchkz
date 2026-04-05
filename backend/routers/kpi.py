import pandas as pd
from fastapi import APIRouter
from fastapi import Query
from services.data_loader import data_loader

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("")
def get_kpi(city: str = Query(...)) -> dict:
    incidents = data_loader.get_incidents(city)
    district_stats = data_loader.get_district_stats(city)

    today = pd.Timestamp.now().normalize()
    ytd_start = pd.Timestamp(year=today.year, month=1, day=1)
    same_period_last_year_end = today - pd.DateOffset(years=1)
    last_year_start = pd.Timestamp(year=today.year - 1, month=1, day=1)

    ytd_incidents = incidents[(incidents["date"] >= ytd_start) & (incidents["date"] <= today)]
    last_year_same_period = incidents[
        (incidents["date"] >= last_year_start) & (incidents["date"] <= same_period_last_year_end)
    ]

    total_incidents_ytd = int(len(ytd_incidents))
    same_period_last_year = int(len(last_year_same_period))

    if same_period_last_year == 0:
        vs_last_year_pct = 0.0
    else:
        vs_last_year_pct = ((total_incidents_ytd - same_period_last_year) / same_period_last_year) * 100

    total_damage_tenge = int(ytd_incidents["damage_tenge"].sum())
    top_cause = (
        ytd_incidents["cause"].value_counts().sort_values(ascending=False).index[0]
        if not ytd_incidents.empty
        else None
    )
    highest_risk_district = (
        district_stats.sort_values("risk_score", ascending=False).iloc[0]["district"]
        if not district_stats.empty
        else None
    )

    return {
        "city": city,
        "total_incidents_ytd": total_incidents_ytd,
        "vs_last_year_pct": round(vs_last_year_pct, 1),
        "total_damage_tenge": total_damage_tenge,
        "highest_risk_district": highest_risk_district,
        "top_cause": top_cause,
        "prevention_potential_tenge": int(round(total_damage_tenge * 0.30)),
        "prevention_potential_incidents": int(round(total_incidents_ytd * 0.30)),
        "roi_note": "Estimated 30% reduction in incidents with AI-driven prevention program",
    }
