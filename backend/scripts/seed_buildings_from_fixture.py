#!/usr/bin/env python3
"""seed_buildings_from_fixture.py — заливает astana_buildings.json в v2 buildings.

Маппинг полей фикстуры → схема buildings (миграция 0009):
  Типизированные:
    id            → id
    city          → city_id
    address       → address (+ address_norm = address.lower())
    name          → name
    district      → district
    object_type   → object_type
    floors_count  → floors_above
    total_area    → total_area_sqm
    lat/lon       → centroid (POINT EWKT)
    source        → source (по умолчанию 'fixture')
  Всё остальное (owner_*, fire_*, контакты, инженерные системы) → details JSONB

Usage:
    cd backend && .venv/bin/python -m scripts.seed_buildings_from_fixture
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add backend/ to path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from db.session import AsyncSessionLocal

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"

# Поля, которые уже хранятся в типизированных колонках — не дублируем в details
_TYPED_KEYS = {
    "id", "city", "address", "name", "district", "object_type",
    "floors_count", "total_area", "lat", "lon", "source",
}


async def seed_city(city: str) -> int:
    path = _FIXTURE_DIR / f"{city}_buildings.json"
    if not path.exists():
        print(f"  ⚠  no fixture: {path}")
        return 0

    items = json.loads(path.read_text(encoding="utf-8"))
    inserted = 0
    async with AsyncSessionLocal() as session:
        # Убедимся, что город существует в cities (FK)
        await session.execute(
            text(
                "INSERT INTO cities (id, code, name) VALUES (:id, :code, :name) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": city, "code": city, "name": city.capitalize()},
        )

        for item in items:
            details = {k: v for k, v in item.items() if k not in _TYPED_KEYS}
            lat = item.get("lat")
            lon = item.get("lon")
            centroid_ewkt = f"SRID=4326;POINT({lon} {lat})" if lat and lon else None

            await session.execute(
                text(
                    """
                    INSERT INTO buildings (
                      id, city_id, address, address_norm,
                      name, district, object_type,
                      floors_above, total_area_sqm, centroid,
                      source, details
                    ) VALUES (
                      :id, :city_id, :address, :address_norm,
                      :name, :district, :object_type,
                      :floors_above, :total_area_sqm, ST_GeomFromEWKT(:centroid),
                      :source, CAST(:details AS JSON)
                    )
                    ON CONFLICT (id) DO UPDATE SET
                      name        = EXCLUDED.name,
                      district    = EXCLUDED.district,
                      object_type = EXCLUDED.object_type,
                      address     = EXCLUDED.address,
                      floors_above= EXCLUDED.floors_above,
                      total_area_sqm = EXCLUDED.total_area_sqm,
                      centroid    = EXCLUDED.centroid,
                      details     = EXCLUDED.details,
                      updated_at  = NOW()
                    """
                ),
                {
                    "id": item["id"],
                    "city_id": item.get("city") or city,
                    "address": item.get("address") or "",
                    "address_norm": (item.get("address") or "").lower(),
                    "name": item.get("name"),
                    "district": item.get("district"),
                    "object_type": item.get("object_type"),
                    "floors_above": item.get("floors_count"),
                    "total_area_sqm": item.get("total_area"),
                    "centroid": centroid_ewkt,
                    "source": item.get("source") or "fixture",
                    "details": json.dumps(details, ensure_ascii=False),
                },
            )
            inserted += 1
        await session.commit()
    return inserted


async def main() -> None:
    total = 0
    for fixture in sorted(_FIXTURE_DIR.glob("*_buildings.json")):
        city = fixture.stem.replace("_buildings", "")
        n = await seed_city(city)
        print(f"  ✓ {city}: {n} buildings")
        total += n
    print(f"\nTotal seeded: {total}")


if __name__ == "__main__":
    asyncio.run(main())
