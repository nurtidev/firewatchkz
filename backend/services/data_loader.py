from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import HTTPException


CITY_CONFIG = {
    "astana": {
        "id": "astana",
        "name": "Астана",
        "center": [51.1801, 71.4460],
        "zoom": 12,
        "data_path": "data/sample/astana_incidents.csv",
        "geojson_path": "backend/data/geojson/astana_districts.geojson",
    }
}

_DATAFRAME_CACHE: dict[str, pd.DataFrame] = {}
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DataLoader:
    def get_incidents(
        self,
        city: str,
        district: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> pd.DataFrame:
        dataframe = self._get_city_dataframe(city)

        filtered = dataframe
        if district:
            filtered = filtered[filtered["district"] == district]
        if date_from:
            start_date = pd.to_datetime(date_from, format="%Y-%m-%d")
            filtered = filtered[filtered["date"] >= start_date]
        if date_to:
            end_date = pd.to_datetime(date_to, format="%Y-%m-%d")
            filtered = filtered[filtered["date"] <= end_date]

        return filtered.copy()

    def get_monthly_counts(self, city: str) -> pd.DataFrame:
        dataframe = self._get_city_dataframe(city)
        monthly_counts = (
            dataframe.assign(year_month=dataframe["date"].dt.to_period("M"))
            .groupby("year_month")
            .size()
            .reset_index(name="count")
            .sort_values("year_month")
            .reset_index(drop=True)
        )
        return monthly_counts

    def get_district_stats(self, city: str) -> pd.DataFrame:
        dataframe = self._get_city_dataframe(city)
        latest_date = dataframe["date"].max()
        last_12_months_start = latest_date - pd.DateOffset(months=12)

        incidents_last_12m = (
            dataframe[dataframe["date"] >= last_12_months_start]
            .groupby("district")
            .size()
            .rename("incidents_last_12m")
        )

        district_stats = (
            dataframe.groupby("district")
            .agg(
                total_incidents=("id", "count"),
                avg_damage_tenge=("damage_tenge", "mean"),
            )
            .reset_index()
        )
        district_stats["avg_damage_tenge"] = district_stats["avg_damage_tenge"].round(0).astype(int)
        district_stats = district_stats.merge(
            incidents_last_12m,
            on="district",
            how="left",
        )
        district_stats["incidents_last_12m"] = district_stats["incidents_last_12m"].fillna(0).astype(int)

        max_incidents = max(district_stats["incidents_last_12m"].max(), 1)
        max_avg_damage = max(district_stats["avg_damage_tenge"].max(), 1)

        district_stats["risk_score"] = (
            (district_stats["incidents_last_12m"] / max_incidents) * 70
            + (district_stats["avg_damage_tenge"] / max_avg_damage) * 30
        ).clip(upper=100)
        district_stats["risk_score"] = district_stats["risk_score"].round(2)

        return district_stats[["district", "total_incidents", "avg_damage_tenge", "risk_score"]].sort_values(
            "district"
        ).reset_index(drop=True)

    def get_cities(self) -> list[dict]:
        cities: list[dict] = []
        for city_id, config in CITY_CONFIG.items():
            incidents = self._get_city_dataframe(city_id)
            cities.append(
                {
                    "id": config["id"],
                    "name": config["name"],
                    "incident_count": int(len(incidents)),
                }
            )
        return cities

    def _get_city_dataframe(self, city: str) -> pd.DataFrame:
        city_key = city.lower()
        if city_key not in CITY_CONFIG:
            raise HTTPException(status_code=404, detail="City not found")

        if city_key not in _DATAFRAME_CACHE:
            _DATAFRAME_CACHE[city_key] = self._load_city_dataframe(city_key)

        return _DATAFRAME_CACHE[city_key]

    def _load_city_dataframe(self, city: str) -> pd.DataFrame:
        csv_path = _PROJECT_ROOT / CITY_CONFIG[city]["data_path"]
        dataframe = pd.read_csv(csv_path)
        dataframe["date"] = pd.to_datetime(dataframe["date"], format="%Y-%m-%d")
        dataframe["casualties"] = dataframe["casualties"].astype(int)
        dataframe["damage_tenge"] = dataframe["damage_tenge"].astype(int)
        return dataframe.sort_values("date").reset_index(drop=True)


data_loader = DataLoader()
