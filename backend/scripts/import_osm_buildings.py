#!/usr/bin/env python3
"""
backend/scripts/import_osm_buildings.py

Bulk-import OSM building polygons for a city into the buildings table.

Usage:
    python3 -m scripts.import_osm_buildings --city astana
    python3 -m scripts.import_osm_buildings --city astana --dry-run
    python3 -m scripts.import_osm_buildings --city astana --bbox "51.05,71.30,51.30,71.60"
    python3 -m scripts.import_osm_buildings --city astana --rows 3 --cols 3
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

# Ensure backend/ is in path when called as module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from services.providers.base import BBox, BuildingDTO, get_provider

# Default bounding box for Astana
ASTANA_BBOX = BBox(min_lat=51.05, min_lon=71.30, max_lat=51.30, max_lon=71.60)


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------

def _split_bbox(bbox: BBox, rows: int = 2, cols: int = 2) -> List[BBox]:
    """Split a BBox into a rows×cols grid for chunked Overpass fetching."""
    lat_step = (bbox.max_lat - bbox.min_lat) / rows
    lon_step = (bbox.max_lon - bbox.min_lon) / cols
    chunks: List[BBox] = []
    for r in range(rows):
        for c in range(cols):
            chunks.append(BBox(
                min_lat=bbox.min_lat + r * lat_step,
                min_lon=bbox.min_lon + c * lon_step,
                max_lat=bbox.min_lat + (r + 1) * lat_step,
                max_lon=bbox.min_lon + (c + 1) * lon_step,
            ))
    return chunks


def _map_osm_type(osm_type: Optional[str]) -> Optional[str]:
    """Map OSM building tag values to our building_type enum."""
    if not osm_type:
        return None
    mapping = {
        "residential": "residential",
        "apartments": "residential",
        "house": "residential",
        "detached": "residential",
        "commercial": "commercial",
        "retail": "commercial",
        "office": "commercial",
        "shop": "commercial",
        "supermarket": "commercial",
        "mall": "commercial",
        "industrial": "industrial",
        "warehouse": "industrial",
        "factory": "industrial",
        "school": "educational",
        "university": "educational",
        "college": "educational",
        "kindergarten": "educational",
        "hospital": "medical",
        "clinic": "medical",
        "doctors": "medical",
        "yes": None,  # generic 'building=yes' — leave null
    }
    return mapping.get(osm_type.lower())


def _dto_to_row(dto: BuildingDTO, city_id: str) -> dict:
    """Convert a BuildingDTO to a dict matching the buildings table columns."""
    return {
        "city_id": city_id,
        "address": dto.address or "",
        "address_norm": (dto.address or "").lower().strip(),
        "geom": dto.geom_wkt,
        "centroid": dto.centroid_wkt,
        "building_type": _map_osm_type(dto.building_type),
        "floors_above": dto.floors_above,
        "height_m": dto.height_m,
        "total_area_sqm": dto.total_area_sqm,
        "year_built": dto.year_built,
        "wall_material": dto.wall_material,
        "source": "osm",
        "external_id": dto.external_id,
    }


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

async def _fetch_with_retry(provider, city_id: str, bbox: BBox, max_retries: int = 3) -> List[BuildingDTO]:
    """Fetch buildings from provider with exponential backoff on failure."""
    for attempt in range(max_retries):
        try:
            return await provider.fetch_buildings(city_id, bbox)
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 30 * (attempt + 1)
            print(f"  Overpass error ({exc}), retrying in {wait}s...")
            await asyncio.sleep(wait)
    return []  # unreachable but satisfies type checker


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

async def upsert_buildings(buildings: List[BuildingDTO], city_id: str) -> None:
    """Bulk-upsert BuildingDTOs into the buildings table using asyncpg."""
    import asyncpg

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://firewatch:firewatch_dev@localhost:5432/firewatch",
    )
    # asyncpg uses plain postgresql:// (not postgresql+asyncpg://)
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn: asyncpg.Connection = await asyncpg.connect(db_url)
    try:
        rows = [_dto_to_row(dto, city_id) for dto in buildings]

        BATCH = 500
        inserted = 0
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            await conn.executemany(
                """
                INSERT INTO buildings
                    (city_id, address, address_norm,
                     geom, centroid,
                     building_type, floors_above, height_m,
                     total_area_sqm, year_built, wall_material,
                     source, external_id, updated_at)
                VALUES (
                    $1, $2, $3,
                    CASE WHEN $4 IS NOT NULL THEN ST_GeomFromText($4, 4326) ELSE NULL END,
                    CASE WHEN $5 IS NOT NULL THEN ST_GeomFromText($5, 4326) ELSE NULL END,
                    $6, $7, $8::numeric,
                    $9::numeric, $10, $11,
                    $12, $13, NOW()
                )
                ON CONFLICT (source, external_id) DO UPDATE SET
                    address        = EXCLUDED.address,
                    address_norm   = EXCLUDED.address_norm,
                    geom           = EXCLUDED.geom,
                    centroid       = EXCLUDED.centroid,
                    building_type  = COALESCE(EXCLUDED.building_type, buildings.building_type),
                    floors_above   = COALESCE(EXCLUDED.floors_above, buildings.floors_above),
                    height_m       = COALESCE(EXCLUDED.height_m, buildings.height_m),
                    updated_at     = NOW()
                """,
                [
                    (
                        r["city_id"],
                        r["address"],
                        r["address_norm"],
                        r["geom"],
                        r["centroid"],
                        r["building_type"],
                        r["floors_above"],
                        r["height_m"],
                        r["total_area_sqm"],
                        r["year_built"],
                        r["wall_material"],
                        r["source"],
                        r["external_id"],
                    )
                    for r in batch
                ],
            )
            inserted += len(batch)
            print(f"  Upserted {inserted}/{len(rows)} buildings...", end="\r")

        print(f"\nDone. Upserted {len(rows)} buildings.")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(city: str, bbox_str: Optional[str], dry_run: bool, rows: int, cols: int) -> None:
    city_id = city  # cities.id == 'astana' per migration 0001

    # Build root BBox
    if bbox_str:
        parts = [float(x.strip()) for x in bbox_str.split(",")]
        if len(parts) != 4:
            print("ERROR: --bbox must be 'min_lat,min_lon,max_lat,max_lon'", file=sys.stderr)
            sys.exit(1)
        min_lat, min_lon, max_lat, max_lon = parts
        root_bbox = BBox(min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon)
    else:
        root_bbox = ASTANA_BBOX

    # Split into sub-bboxes for chunked fetching (avoids Overpass timeouts)
    chunks = _split_bbox(root_bbox, rows=rows, cols=cols)
    print(f"Fetching buildings for city='{city_id}' in {len(chunks)} chunk(s) ({rows}x{cols} grid)")

    provider = get_provider("osm")

    all_buildings: List[BuildingDTO] = []
    seen_ids: set = set()

    for idx, chunk in enumerate(chunks, start=1):
        print(f"  Chunk {idx}/{len(chunks)}: {chunk.to_overpass()}")
        chunk_buildings = await _fetch_with_retry(provider, city_id, chunk)
        # Deduplicate across chunks by external_id
        new_count = 0
        for b in chunk_buildings:
            if b.external_id not in seen_ids:
                seen_ids.add(b.external_id)
                all_buildings.append(b)
                new_count += 1
        print(f"    Got {len(chunk_buildings)} buildings ({new_count} new, {len(chunk_buildings) - new_count} duplicates)")

    print(f"Total unique buildings fetched: {len(all_buildings)}")

    if dry_run:
        print("Dry run — not inserting into database.")
        return

    await upsert_buildings(all_buildings, city_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import OSM buildings into the FireWatch buildings table."
    )
    parser.add_argument(
        "--city",
        required=True,
        help="City id, e.g. 'astana'",
    )
    parser.add_argument(
        "--bbox",
        default=None,
        help="Custom bounding box: 'min_lat,min_lon,max_lat,max_lon'",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and count buildings but do not write to the database",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=2,
        help="Grid rows for bbox chunking (default: 2)",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=2,
        help="Grid columns for bbox chunking (default: 2)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(
        city=args.city,
        bbox_str=args.bbox,
        dry_run=args.dry_run,
        rows=args.rows,
        cols=args.cols,
    ))
