from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = _BACKEND_ROOT / "migrations"
_SEED_DIR = _BACKEND_ROOT / "data" / "sample"

load_dotenv()


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

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute("SELECT version FROM schema_migrations")
                applied_versions = {row["version"] for row in cursor.fetchall()}

                for migration_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                    version = migration_file.name
                    if version in applied_versions:
                        continue
                    cursor.execute(migration_file.read_text(encoding="utf-8"))
                    cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            connection.commit()

    def seed_buildings(self) -> None:
        if not self.is_configured():
            return

        seed_path = _SEED_DIR / "astana_buildings.json"
        payload = json.loads(seed_path.read_text(encoding="utf-8"))

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                for item in payload:
                    cursor.execute(
                        """
                        INSERT INTO buildings (
                            city,
                            district,
                            name,
                            address,
                            object_type,
                            document_type,
                            category,
                            fire_resistance_degree,
                            floors_count,
                            total_area,
                            construction_type,
                            nearest_fire_department,
                            distance_to_fire_department,
                            arrival_time_minutes,
                            route_description,
                            fire_rank,
                            owner_name,
                            owner_phone,
                            technical_manager_name,
                            technical_manager_phone,
                            security_phone,
                            dispatcher_phone,
                            private_fire_service_phone,
                            power_supply_info,
                            heating_info,
                            water_supply_info,
                            ventilation_info,
                            smoke_removal_info,
                            fire_alarm_info,
                            fire_extinguishing_systems,
                            evacuation_routes_count,
                            potential_hazards,
                            complexity_features,
                            auxiliary_means,
                            estimated_forces,
                            lat,
                            lon,
                            source
                        )
                        VALUES (
                            %(city)s,
                            %(district)s,
                            %(name)s,
                            %(address)s,
                            %(object_type)s,
                            %(document_type)s,
                            %(category)s,
                            %(fire_resistance_degree)s,
                            %(floors_count)s,
                            %(total_area)s,
                            %(construction_type)s,
                            %(nearest_fire_department)s,
                            %(distance_to_fire_department)s,
                            %(arrival_time_minutes)s,
                            %(route_description)s,
                            %(fire_rank)s,
                            %(owner_name)s,
                            %(owner_phone)s,
                            %(technical_manager_name)s,
                            %(technical_manager_phone)s,
                            %(security_phone)s,
                            %(dispatcher_phone)s,
                            %(private_fire_service_phone)s,
                            %(power_supply_info)s,
                            %(heating_info)s,
                            %(water_supply_info)s,
                            %(ventilation_info)s,
                            %(smoke_removal_info)s,
                            %(fire_alarm_info)s,
                            %(fire_extinguishing_systems)s::jsonb,
                            %(evacuation_routes_count)s,
                            %(potential_hazards)s,
                            %(complexity_features)s,
                            %(auxiliary_means)s,
                            %(estimated_forces)s::jsonb,
                            %(lat)s,
                            %(lon)s,
                            %(source)s
                        )
                        ON CONFLICT (city, name) DO UPDATE SET
                            district = EXCLUDED.district,
                            address = EXCLUDED.address,
                            object_type = EXCLUDED.object_type,
                            document_type = EXCLUDED.document_type,
                            category = EXCLUDED.category,
                            fire_resistance_degree = EXCLUDED.fire_resistance_degree,
                            floors_count = EXCLUDED.floors_count,
                            total_area = EXCLUDED.total_area,
                            construction_type = EXCLUDED.construction_type,
                            nearest_fire_department = EXCLUDED.nearest_fire_department,
                            distance_to_fire_department = EXCLUDED.distance_to_fire_department,
                            arrival_time_minutes = EXCLUDED.arrival_time_minutes,
                            route_description = EXCLUDED.route_description,
                            fire_rank = EXCLUDED.fire_rank,
                            owner_name = EXCLUDED.owner_name,
                            owner_phone = EXCLUDED.owner_phone,
                            technical_manager_name = EXCLUDED.technical_manager_name,
                            technical_manager_phone = EXCLUDED.technical_manager_phone,
                            security_phone = EXCLUDED.security_phone,
                            dispatcher_phone = EXCLUDED.dispatcher_phone,
                            private_fire_service_phone = EXCLUDED.private_fire_service_phone,
                            power_supply_info = EXCLUDED.power_supply_info,
                            heating_info = EXCLUDED.heating_info,
                            water_supply_info = EXCLUDED.water_supply_info,
                            ventilation_info = EXCLUDED.ventilation_info,
                            smoke_removal_info = EXCLUDED.smoke_removal_info,
                            fire_alarm_info = EXCLUDED.fire_alarm_info,
                            fire_extinguishing_systems = EXCLUDED.fire_extinguishing_systems,
                            evacuation_routes_count = EXCLUDED.evacuation_routes_count,
                            potential_hazards = EXCLUDED.potential_hazards,
                            complexity_features = EXCLUDED.complexity_features,
                            auxiliary_means = EXCLUDED.auxiliary_means,
                            estimated_forces = EXCLUDED.estimated_forces,
                            lat = EXCLUDED.lat,
                            lon = EXCLUDED.lon,
                            source = EXCLUDED.source,
                            updated_at = NOW()
                        """,
                        {
                            **item,
                            "fire_extinguishing_systems": json.dumps(item.get("fire_extinguishing_systems") or {}),
                            "estimated_forces": json.dumps(item.get("estimated_forces") or {}),
                        },
                    )
            connection.commit()

    def get_buildings(self, city: str) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        city,
                        district,
                        name,
                        address,
                        object_type,
                        document_type,
                        category,
                        fire_resistance_degree,
                        floors_count,
                        total_area,
                        construction_type,
                        nearest_fire_department,
                        distance_to_fire_department,
                        arrival_time_minutes,
                        route_description,
                        fire_rank,
                        owner_name,
                        owner_phone,
                        technical_manager_name,
                        technical_manager_phone,
                        security_phone,
                        dispatcher_phone,
                        private_fire_service_phone,
                        power_supply_info,
                        heating_info,
                        water_supply_info,
                        ventilation_info,
                        smoke_removal_info,
                        fire_alarm_info,
                        fire_extinguishing_systems,
                        evacuation_routes_count,
                        potential_hazards,
                        complexity_features,
                        auxiliary_means,
                        estimated_forces,
                        lat,
                        lon,
                        source
                    FROM buildings
                    WHERE city = %s
                    ORDER BY floors_count DESC NULLS LAST, arrival_time_minutes DESC NULLS LAST, name ASC
                    """,
                    (city.lower(),),
                )
                rows = cursor.fetchall()

        for row in rows:
            if isinstance(row.get("fire_extinguishing_systems"), str):
                row["fire_extinguishing_systems"] = json.loads(row["fire_extinguishing_systems"])
            if isinstance(row.get("estimated_forces"), str):
                row["estimated_forces"] = json.loads(row["estimated_forces"])
        return rows


database_service = DatabaseService()
