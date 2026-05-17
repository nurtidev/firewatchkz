#!/usr/bin/env python3
"""
One-time migration: seed PostgreSQL from v1 CSV/JSON sample data.
Idempotent — safe to run multiple times.

Usage: python3 backend/scripts/migrate_csv_to_db.py
"""
import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Any

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "backend" / "data" / "sample"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://firewatch:firewatch_dev@localhost:5432/firewatch",
)
# asyncpg uses plain postgresql:// not postgresql+asyncpg://
DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def migrate_incidents(conn: asyncpg.Connection) -> int:
    """
    Migrate incidents from astana_incidents.csv.

    CSV columns: id, date, city, district, building_type, cause, severity,
                 casualties, damage_tenge, lat, lon

    Uses the CSV id as the PK so that operations.incident_id FK resolves.
    Idempotency: unique index on (source, external_id) created first;
    rows already present are skipped via ON CONFLICT DO NOTHING.
    """
    # No index needed — we insert with explicit id (PK), so ON CONFLICT (id) suffices

    path = DATA_DIR / "astana_incidents.csv"
    rows: List[Tuple[Any, ...]] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse date — CSV format is YYYY-MM-DD
            try:
                occurred_at = datetime.strptime(
                    row["date"].strip(), "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                occurred_at = datetime.now(timezone.utc)

            lat = float(row["lat"]) if row.get("lat") else None
            lon = float(row["lon"]) if row.get("lon") else None

            # Use CSV id as both PK and external_id to preserve FK from operations
            rows.append((
                row["id"],                                      # $1  id (PK override)
                occurred_at,                                    # $2  occurred_at
                row.get("district", ""),                        # $3  district
                row.get("building_type", ""),                   # $4  building_type
                row.get("cause", ""),                           # $5  cause
                row.get("severity", ""),                        # $6  severity
                float(row["damage_tenge"]) if row.get("damage_tenge") else None,  # $7
                int(row["casualties"]) if row.get("casualties") else 0,           # $8
                lat,                                            # $9  lat
                lon,                                            # $10 lon
                row.get("city", "astana"),                      # $11 city (address_text)
                row["id"],                                      # $12 external_id
            ))

    if not rows:
        return 0

    await conn.executemany("""
        INSERT INTO incidents
            (id, occurred_at, district, building_type, cause, severity,
             damage_tenge, casualties, lat, lon, source,
             address_text, external_id,
             geom)
        VALUES (
            $1, $2, $3, $4, $5, $6, $7::numeric, $8, $9::numeric, $10::numeric, 'csv',
            $11, $12,
            CASE WHEN $9 IS NOT NULL AND $10 IS NOT NULL
                 THEN ST_SetSRID(ST_MakePoint($10::double precision, $9::double precision), 4326)
                 ELSE NULL END
        )
        ON CONFLICT (id) DO NOTHING
    """, rows)

    return len(rows)


async def migrate_hydrants(conn: asyncpg.Connection) -> int:
    """
    Migrate hydrants from astana_hydrants.json.

    JSON fields: id, city, district, address, lat, lon, status,
                 last_checked, winter_accessible, pressure_bar, notes

    Idempotency: unique index on external_id created first.
    """
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hydrants_external_id
        ON hydrants (external_id)
        WHERE external_id IS NOT NULL
    """)

    path = DATA_DIR / "astana_hydrants.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    rows: List[Tuple[Any, ...]] = []
    for h in data:
        lat = float(h["lat"]) if h.get("lat") is not None else None
        lon = float(h["lon"]) if h.get("lon") is not None else None

        # Map last_checked → last_check_at (TIMESTAMPTZ)
        last_check_at: Optional[datetime] = None
        if h.get("last_checked"):
            try:
                last_check_at = datetime.strptime(
                    h["last_checked"], "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        rows.append((
            h.get("id", ""),                            # $1  external_id
            h.get("city", "astana"),                    # $2  city
            h.get("district", ""),                      # $3  district
            h.get("address", ""),                       # $4  address
            h.get("status", "working"),                 # $5  status
            lat,                                        # $6  lat
            lon,                                        # $7  lon
            last_check_at,                              # $8  last_check_at
            bool(h.get("winter_accessible", True)),     # $9  winter_access
        ))

    if not rows:
        return 0

    await conn.executemany("""
        INSERT INTO hydrants
            (external_id, city, district, address, status, lat, lon,
             last_check_at, winter_access,
             geom)
        VALUES (
            $1, $2, $3, $4, $5, $6::numeric, $7::numeric, $8, $9,
            CASE WHEN $6 IS NOT NULL AND $7 IS NOT NULL
                 THEN ST_SetSRID(ST_MakePoint($7::double precision, $6::double precision), 4326)
                 ELSE NULL END
        )
        ON CONFLICT (external_id) WHERE external_id IS NOT NULL DO NOTHING
    """, rows)

    return len(rows)


async def migrate_stations(conn: asyncpg.Connection) -> int:
    """
    Migrate fire stations from astana_stations.json.

    JSON fields: id, city, name, district, lat, lon, units, staff_count

    fire_stations.id is an explicit PK (not auto-generated), so
    ON CONFLICT (id) DO NOTHING works directly.
    """
    path = DATA_DIR / "astana_stations.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    rows: List[Tuple[Any, ...]] = []
    for s in data:
        lat = float(s["lat"]) if s.get("lat") is not None else None
        lon = float(s["lon"]) if s.get("lon") is not None else None
        rows.append((
            s["id"],                                    # $1  id (PK)
            s.get("city", "astana"),                    # $2  city
            s.get("name", ""),                          # $3  name
            s.get("district", ""),                      # $4  district
            int(s["units"]) if s.get("units") is not None else None,        # $5
            int(s["staff_count"]) if s.get("staff_count") is not None else None,  # $6
            lat,                                        # $7  lat
            lon,                                        # $8  lon
        ))

    if not rows:
        return 0

    await conn.executemany("""
        INSERT INTO fire_stations
            (id, city, name, district, units, staff_count, lat, lon,
             geom)
        VALUES (
            $1, $2, $3, $4, $5, $6, $7::numeric, $8::numeric,
            CASE WHEN $7 IS NOT NULL AND $8 IS NOT NULL
                 THEN ST_SetSRID(ST_MakePoint($8::double precision, $7::double precision), 4326)
                 ELSE NULL END
        )
        ON CONFLICT (id) DO NOTHING
    """, rows)

    return len(rows)


async def migrate_operations(conn: asyncpg.Connection) -> int:
    """
    Migrate operations from astana_operations.csv.

    CSV columns: id, date, city, district, station_id, incident_id,
                 response_time_min, outcome, notes

    Uses CSV id as PK. station_id and incident_id are kept as-is;
    they reference fire_stations.id and incidents.id respectively.
    Both FKs are nullable so mismatches are silently ignored.

    Idempotency: ON CONFLICT (id) DO NOTHING (id is PK).
    """
    path = DATA_DIR / "astana_operations.csv"
    rows: List[Tuple[Any, ...]] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date = datetime.strptime(
                    row["date"].strip(), "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                date = None

            rows.append((
                row["id"],                                                      # $1  id (PK)
                date,                                                           # $2  date
                row.get("city", "astana"),                                      # $3  city
                row.get("district", ""),                                        # $4  district
                row.get("station_id") or None,                                  # $5  station_id
                row.get("incident_id") or None,                                 # $6  incident_id
                float(row["response_time_min"]) if row.get("response_time_min") else None,  # $7
                row.get("outcome", ""),                                         # $8  outcome
                row.get("notes", "") or None,                                   # $9  notes
            ))

    if not rows:
        return 0

    # Use subselects so missing station/incident FK refs become NULL (sample data mismatch)
    await conn.executemany("""
        INSERT INTO operations
            (id, date, city, district, station_id, incident_id,
             response_time_min, outcome, notes)
        VALUES (
            $1, $2, $3, $4,
            (SELECT id FROM fire_stations WHERE id = $5 LIMIT 1),
            (SELECT id FROM incidents WHERE id = $6 LIMIT 1),
            $7, $8, $9
        )
        ON CONFLICT (id) DO NOTHING
    """, rows)

    return len(rows)


async def main() -> None:
    print(f"Connecting to DB: {DATABASE_URL.split('@')[-1]}")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Migrating incidents...", end=" ", flush=True)
        n = await migrate_incidents(conn)
        print(f"done ({n} rows)")

        print("Migrating hydrants...", end=" ", flush=True)
        n = await migrate_hydrants(conn)
        print(f"done ({n} rows)")

        print("Migrating fire stations...", end=" ", flush=True)
        n = await migrate_stations(conn)
        print(f"done ({n} rows)")

        print("Migrating operations...", end=" ", flush=True)
        n = await migrate_operations(conn)
        print(f"done ({n} rows)")

        print("\nVerification:")
        for table in ["incidents", "hydrants", "fire_stations", "operations"]:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table}: {count} rows")

        print("\nMigration complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
