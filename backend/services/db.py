from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = _BACKEND_ROOT / "migrations"
_SEED_DIR = _BACKEND_ROOT / "data" / "sample"

load_dotenv()

# ─── Synthetic data constants (mirrors generate_data.py) ─────────────────────

_DISTRICTS: dict[str, dict] = {
    "Есіл": {
        "lat_range": (51.15, 51.22), "lon_range": (71.40, 71.55), "weight": 0.24,
        "building_weights": {"residential": 0.34, "commercial": 0.33, "industrial": 0.08, "construction": 0.18, "other": 0.07},
        "cause_weights": {"electrical": 0.40, "open_flame": 0.24, "arson": 0.08, "children": 0.05, "other": 0.23},
        "severity_weights": {"low": 0.51, "medium": 0.31, "high": 0.14, "critical": 0.04},
        "station": "ПЧ-1", "base_response_min": 5.5,
    },
    "Алматы": {
        "lat_range": (51.17, 51.25), "lon_range": (71.28, 71.42), "weight": 0.21,
        "building_weights": {"residential": 0.43, "commercial": 0.22, "industrial": 0.10, "construction": 0.15, "other": 0.10},
        "cause_weights": {"electrical": 0.30, "open_flame": 0.26, "arson": 0.10, "children": 0.12, "other": 0.22},
        "severity_weights": {"low": 0.56, "medium": 0.27, "high": 0.13, "critical": 0.04},
        "station": "ПЧ-2", "base_response_min": 6.2,
    },
    "Байқоңыр": {
        "lat_range": (51.10, 51.18), "lon_range": (71.35, 71.45), "weight": 0.18,
        "building_weights": {"residential": 0.28, "commercial": 0.18, "industrial": 0.31, "construction": 0.13, "other": 0.10},
        "cause_weights": {"electrical": 0.29, "open_flame": 0.24, "arson": 0.11, "children": 0.06, "other": 0.30},
        "severity_weights": {"low": 0.38, "medium": 0.31, "high": 0.21, "critical": 0.10},
        "station": "ПЧ-3", "base_response_min": 7.8,
    },
    "Сарыарқа": {
        "lat_range": (51.18, 51.28), "lon_range": (71.42, 71.58), "weight": 0.22,
        "building_weights": {"residential": 0.41, "commercial": 0.25, "industrial": 0.09, "construction": 0.15, "other": 0.10},
        "cause_weights": {"electrical": 0.28, "open_flame": 0.28, "arson": 0.10, "children": 0.09, "other": 0.25},
        "severity_weights": {"low": 0.54, "medium": 0.29, "high": 0.13, "critical": 0.04},
        "station": "ПЧ-4", "base_response_min": 6.8,
    },
    "Нұра": {
        "lat_range": (51.08, 51.16), "lon_range": (71.45, 71.58), "weight": 0.15,
        "building_weights": {"residential": 0.39, "commercial": 0.19, "industrial": 0.12, "construction": 0.20, "other": 0.10},
        "cause_weights": {"electrical": 0.27, "open_flame": 0.27, "arson": 0.08, "children": 0.08, "other": 0.30},
        "severity_weights": {"low": 0.52, "medium": 0.30, "high": 0.14, "critical": 0.04},
        "station": "ПЧ-5", "base_response_min": 8.5,
    },
}

_SEVERITY_DAMAGE: dict[str, tuple[int, int]] = {
    "low": (50_000, 500_000),
    "medium": (500_000, 5_000_000),
    "high": (5_000_000, 50_000_000),
    "critical": (50_000_000, 500_000_000),
}

_SEVERITY_UNITS: dict[str, tuple[int, int]] = {
    "low": (1, 2),
    "medium": (2, 3),
    "high": (3, 5),
    "critical": (4, 7),
}

_OUTCOMES = ["contained", "contained", "contained", "escalated", "total_loss"]
_OUTCOME_WEIGHTS = [0.55, 0.20, 0.15, 0.07, 0.03]

_CASUALTY_VALUES = np.arange(0, 11)
_CASUALTY_WEIGHTS = np.array([0.63, 0.17, 0.08, 0.04, 0.025, 0.018, 0.012, 0.009, 0.007, 0.005, 0.004])
_CASUALTY_WEIGHTS = _CASUALTY_WEIGHTS / _CASUALTY_WEIGHTS.sum()


def _weighted_choice(rng: np.random.Generator, options: dict[str, float]) -> str:
    keys = list(options.keys())
    w = np.array(list(options.values()), dtype=float)
    w /= w.sum()
    return str(rng.choice(keys, p=w))


def _month_weight(month: int) -> float:
    return 2.0 if month in {1, 2, 5, 6} else 1.0


def _generate_incidents_and_operations(city: str, years: int = 5, seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng = np.random.default_rng(seed)
    end_date = date.today()
    start_date = end_date - timedelta(days=years * 365)
    all_dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    weights = np.array([_month_weight(d.month) for d in all_dates], dtype=float)
    weights /= weights.sum()

    # ~300-400 incidents per year
    count = int(rng.integers(300, 401) * years)
    sampled = rng.choice(all_dates, size=count, p=weights, replace=True)

    district_names = list(_DISTRICTS.keys())
    district_weights = np.array([_DISTRICTS[d]["weight"] for d in district_names], dtype=float)
    district_weights /= district_weights.sum()

    incidents: list[dict] = []
    operations: list[dict] = []

    for idx, incident_date in enumerate(sorted(sampled), start=1):
        if hasattr(incident_date, "item"):
            incident_date = incident_date.item()

        district = str(rng.choice(district_names, p=district_weights))
        dconf = _DISTRICTS[district]

        # building type (weekend bias toward residential)
        bw = dconf["building_weights"].copy()
        if incident_date.weekday() >= 5:
            bw["residential"] = bw.get("residential", 0) + 0.20
        building_type = _weighted_choice(rng, bw)

        # cause
        cw = dconf["cause_weights"].copy()
        if building_type == "residential" and incident_date.month in {1, 2}:
            cw["open_flame"] = cw.get("open_flame", 0) + 0.05
            cw["children"] = cw.get("children", 0) + 0.03
        if building_type == "commercial":
            cw["electrical"] = cw.get("electrical", 0) + 0.04
        cause = _weighted_choice(rng, cw)

        # severity
        sw = dconf["severity_weights"].copy()
        if building_type == "industrial":
            sw["high"] = sw.get("high", 0) + 0.06
            sw["critical"] = sw.get("critical", 0) + 0.04
        if cause == "arson":
            sw["medium"] = sw.get("medium", 0) + 0.03
            sw["high"] = sw.get("high", 0) + 0.03
        severity = _weighted_choice(rng, sw)

        casualties = int(rng.choice(_CASUALTY_VALUES, p=_CASUALTY_WEIGHTS))
        dmg_lo, dmg_hi = _SEVERITY_DAMAGE[severity]
        damage_tenge = int(rng.integers(dmg_lo, dmg_hi + 1))

        lat_lo, lat_hi = dconf["lat_range"]
        lon_lo, lon_hi = dconf["lon_range"]
        lat = round(float(rng.uniform(lat_lo, lat_hi)), 6)
        lon = round(float(rng.uniform(lon_lo, lon_hi)), 6)

        incident_id = f"ast-{incident_date:%Y%m%d}-{idx:05d}"
        incidents.append({
            "id": incident_id,
            "date": incident_date.isoformat(),
            "city": city,
            "district": district,
            "building_type": building_type,
            "cause": cause,
            "severity": severity,
            "casualties": casualties,
            "damage_tenge": damage_tenge,
            "lat": lat,
            "lon": lon,
        })

        # response time: base + noise, higher for critical
        severity_penalty = {"low": 0.0, "medium": 0.5, "high": 1.2, "critical": 2.5}[severity]
        # night calls (22:00-06:00) add 1-2 min
        hour = int(rng.integers(0, 24))
        night_penalty = float(rng.uniform(1.0, 2.0)) if (hour >= 22 or hour < 6) else 0.0
        response_time = round(
            dconf["base_response_min"] + severity_penalty + night_penalty + float(rng.uniform(-1.0, 2.5)),
            1,
        )
        response_time = max(2.0, response_time)

        units_lo, units_hi = _SEVERITY_UNITS[severity]
        units = int(rng.integers(units_lo, units_hi + 1))

        outcome_weights = np.array(_OUTCOME_WEIGHTS, dtype=float)
        if severity == "critical":
            outcome_weights = np.array([0.25, 0.15, 0.20, 0.25, 0.15])
        outcome_weights /= outcome_weights.sum()
        outcome = str(rng.choice(_OUTCOMES, p=outcome_weights))

        operations.append({
            "id": f"op-{incident_id}",
            "date": incident_date.isoformat(),
            "city": city,
            "district": district,
            "station_id": dconf["station"],
            "incident_id": incident_id,
            "response_time_min": response_time,
            "outcome": outcome,
            "units_dispatched": units,
        })

    return incidents, operations


# ─── DatabaseService ──────────────────────────────────────────────────────────

class DatabaseService:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()

    def is_configured(self) -> bool:
        return bool(self.database_url)

    def get_connection(self) -> psycopg.Connection:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def apply_migrations(self) -> None:
        if not self.is_configured():
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute("SELECT version FROM schema_migrations")
                applied = {row["version"] for row in cur.fetchall()}

                for migration_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                    version = migration_file.name
                    if version in applied:
                        continue
                    cur.execute(migration_file.read_text(encoding="utf-8"))
                    cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()

    def seed_buildings(self) -> None:
        if not self.is_configured():
            return

        seed_path = _SEED_DIR / "astana_buildings.json"
        payload = json.loads(seed_path.read_text(encoding="utf-8"))

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for item in payload:
                    cur.execute(
                        """
                        INSERT INTO buildings (
                            city, district, name, address, object_type, document_type,
                            category, fire_resistance_degree, floors_count, total_area,
                            construction_type, nearest_fire_department, distance_to_fire_department,
                            arrival_time_minutes, route_description, fire_rank,
                            owner_name, owner_phone, technical_manager_name, technical_manager_phone,
                            security_phone, dispatcher_phone, private_fire_service_phone,
                            power_supply_info, heating_info, water_supply_info, ventilation_info,
                            smoke_removal_info, fire_alarm_info, fire_extinguishing_systems,
                            evacuation_routes_count, potential_hazards, complexity_features,
                            auxiliary_means, estimated_forces, lat, lon, source
                        )
                        VALUES (
                            %(city)s, %(district)s, %(name)s, %(address)s, %(object_type)s,
                            %(document_type)s, %(category)s, %(fire_resistance_degree)s,
                            %(floors_count)s, %(total_area)s, %(construction_type)s,
                            %(nearest_fire_department)s, %(distance_to_fire_department)s,
                            %(arrival_time_minutes)s, %(route_description)s, %(fire_rank)s,
                            %(owner_name)s, %(owner_phone)s, %(technical_manager_name)s,
                            %(technical_manager_phone)s, %(security_phone)s, %(dispatcher_phone)s,
                            %(private_fire_service_phone)s, %(power_supply_info)s, %(heating_info)s,
                            %(water_supply_info)s, %(ventilation_info)s, %(smoke_removal_info)s,
                            %(fire_alarm_info)s, %(fire_extinguishing_systems)s::jsonb,
                            %(evacuation_routes_count)s, %(potential_hazards)s, %(complexity_features)s,
                            %(auxiliary_means)s, %(estimated_forces)s::jsonb, %(lat)s, %(lon)s, %(source)s
                        )
                        ON CONFLICT (city, name) DO UPDATE SET
                            district = EXCLUDED.district, address = EXCLUDED.address,
                            updated_at = NOW()
                        """,
                        {
                            **item,
                            "fire_extinguishing_systems": json.dumps(item.get("fire_extinguishing_systems") or {}),
                            "estimated_forces": json.dumps(item.get("estimated_forces") or {}),
                        },
                    )
            conn.commit()

    def seed_incidents(self, city: str = "astana", years: int = 5) -> None:
        if not self.is_configured():
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM incidents WHERE city = %s", (city,))
                row = cur.fetchone()
                if row and row["cnt"] > 0:
                    return  # already seeded

            incidents, _ = _generate_incidents_and_operations(city, years=years)
            with conn.cursor() as cur:
                for inc in incidents:
                    cur.execute(
                        """
                        INSERT INTO incidents (id, date, city, district, building_type, cause,
                            severity, casualties, damage_tenge, lat, lon)
                        VALUES (%(id)s, %(date)s, %(city)s, %(district)s, %(building_type)s,
                            %(cause)s, %(severity)s, %(casualties)s, %(damage_tenge)s, %(lat)s, %(lon)s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        inc,
                    )
            conn.commit()
            print(f"[db] Seeded {len(incidents)} incidents for {city}", file=sys.stderr)

    def seed_operations(self, city: str = "astana", years: int = 5) -> None:
        if not self.is_configured():
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM operations WHERE city = %s", (city,))
                row = cur.fetchone()
                if row and row["cnt"] > 0:
                    return  # already seeded

            _, operations = _generate_incidents_and_operations(city, years=years)
            with conn.cursor() as cur:
                for op in operations:
                    cur.execute(
                        """
                        INSERT INTO operations (id, date, city, district, station_id, incident_id,
                            response_time_min, outcome, units_dispatched)
                        VALUES (%(id)s, %(date)s, %(city)s, %(district)s, %(station_id)s,
                            %(incident_id)s, %(response_time_min)s, %(outcome)s, %(units_dispatched)s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        op,
                    )
            conn.commit()
            print(f"[db] Seeded {len(operations)} operations for {city}", file=sys.stderr)

    def get_incidents_df(self, city: str) -> pd.DataFrame | None:
        if not self.is_configured():
            return None
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, date, city, district, building_type, cause, severity,
                           casualties, damage_tenge, lat, lon
                    FROM incidents WHERE city = %s ORDER BY date
                    """,
                    (city.lower(),),
                )
                rows = cur.fetchall()
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["casualties"] = df["casualties"].astype(int)
        df["damage_tenge"] = df["damage_tenge"].astype(int)
        return df

    def get_operations_df(self, city: str) -> pd.DataFrame | None:
        if not self.is_configured():
            return None
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, date, city, district, station_id, incident_id,
                           response_time_min, outcome, units_dispatched
                    FROM operations WHERE city = %s ORDER BY date
                    """,
                    (city.lower(),),
                )
                rows = cur.fetchall()
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["response_time_min"] = df["response_time_min"].astype(float)
        return df

    def get_buildings(self, city: str) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, city, district, name, address, object_type, document_type,
                        category, fire_resistance_degree, floors_count, total_area,
                        construction_type, nearest_fire_department, distance_to_fire_department,
                        arrival_time_minutes, route_description, fire_rank,
                        owner_name, owner_phone, technical_manager_name, technical_manager_phone,
                        security_phone, dispatcher_phone, private_fire_service_phone,
                        power_supply_info, heating_info, water_supply_info, ventilation_info,
                        smoke_removal_info, fire_alarm_info, fire_extinguishing_systems,
                        evacuation_routes_count, potential_hazards, complexity_features,
                        auxiliary_means, estimated_forces, lat, lon, source
                    FROM buildings
                    WHERE city = %s
                    ORDER BY floors_count DESC NULLS LAST, arrival_time_minutes DESC NULLS LAST, name ASC
                    """,
                    (city.lower(),),
                )
                rows = cur.fetchall()

        for row in rows:
            if isinstance(row.get("fire_extinguishing_systems"), str):
                row["fire_extinguishing_systems"] = json.loads(row["fire_extinguishing_systems"])
            if isinstance(row.get("estimated_forces"), str):
                row["estimated_forces"] = json.loads(row["estimated_forces"])
        return rows

    def get_building_by_id(self, building_id: str) -> Optional[dict[str, Any]]:
        if not self.is_configured():
            return None
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, city, district, name, address, object_type, document_type,
                        category, fire_resistance_degree, floors_count, total_area,
                        construction_type, nearest_fire_department, distance_to_fire_department,
                        arrival_time_minutes, route_description, fire_rank,
                        owner_name, owner_phone, technical_manager_name, technical_manager_phone,
                        security_phone, dispatcher_phone, private_fire_service_phone,
                        power_supply_info, heating_info, water_supply_info, ventilation_info,
                        smoke_removal_info, fire_alarm_info, fire_extinguishing_systems,
                        evacuation_routes_count, potential_hazards, complexity_features,
                        auxiliary_means, estimated_forces, lat, lon, source
                    FROM buildings WHERE id::text = %s
                    """,
                    (building_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        if isinstance(row.get("fire_extinguishing_systems"), str):
            row["fire_extinguishing_systems"] = json.loads(row["fire_extinguishing_systems"])
        if isinstance(row.get("estimated_forces"), str):
            row["estimated_forces"] = json.loads(row["estimated_forces"])
        return row


database_service = DatabaseService()
