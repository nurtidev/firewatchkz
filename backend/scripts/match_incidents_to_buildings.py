#!/usr/bin/env python3
"""
backend/scripts/match_incidents_to_buildings.py

Matches incidents to the nearest building within 30 m using PostGIS.
Fills incidents.building_id for rows where it is NULL.

Idempotent — safe to run multiple times (only touches rows where building_id IS NULL).

Usage:
    python3 -m scripts.match_incidents_to_buildings
    python3 -m scripts.match_incidents_to_buildings --dry-run

Exit codes:
    0 — >=70% of incidents matched (or dry-run completed)
    1 — <70% of incidents matched
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure backend/ is in path when called as module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://firewatch:firewatch_dev@localhost:5432/firewatch",
)
# asyncpg uses plain postgresql:// — strip the +asyncpg driver prefix
DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# ──────────────────────────────────────────────────────────────────────────────
# Pure helpers (importable without DB, tested in unit tests)
# ──────────────────────────────────────────────────────────────────────────────

MATCH_SQL = """
UPDATE incidents i
SET building_id = (
    SELECT b.id FROM buildings b
    WHERE ST_DWithin(b.geom::geography, i.geom::geography, 30)
    ORDER BY ST_Distance(b.geom, i.geom)
    LIMIT 1
)
WHERE building_id IS NULL;
"""


def compute_exit_code(total: int, matched: int) -> int:
    """Return 0 if >=70% matched, 1 otherwise."""
    if total == 0:
        # Nothing to match — consider it success
        return 0
    pct = matched / total
    return 0 if pct >= 0.70 else 1


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Match incidents to nearest buildings via PostGIS (fills building_id)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts without running the UPDATE.",
    )
    return parser


# ──────────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_counts(conn: "asyncpg.Connection") -> tuple:  # type: ignore[name-defined]
    """Return (total, already_matched, unmatched)."""
    total: int = await conn.fetchval("SELECT COUNT(*) FROM incidents")
    unmatched: int = await conn.fetchval(
        "SELECT COUNT(*) FROM incidents WHERE building_id IS NULL"
    )
    already_matched: int = total - unmatched
    return total, already_matched, unmatched


async def run_match(conn: "asyncpg.Connection") -> None:  # type: ignore[name-defined]
    """Execute the UPDATE that assigns building_id."""
    await conn.execute(MATCH_SQL)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def main(dry_run: bool = False) -> int:
    import asyncpg  # imported here so the module can be imported without asyncpg installed

    print(f"Connecting to DB: {DATABASE_URL.split('@')[-1]}")
    conn: asyncpg.Connection = await asyncpg.connect(DATABASE_URL)
    try:
        total, already_matched, unmatched = await fetch_counts(conn)
        print(f"Total incidents     : {total}")
        print(f"Already matched     : {already_matched}")
        print(f"Unmatched (NULL)    : {unmatched}")

        if dry_run:
            print("\n[dry-run] Skipping UPDATE — no changes written.")
            newly_matched = 0
        else:
            if unmatched == 0:
                print("\nAll incidents already matched. Nothing to do.")
                newly_matched = 0
            else:
                print("\nRunning spatial match UPDATE…", end=" ", flush=True)
                await run_match(conn)
                print("done.")

                _, after_matched, after_unmatched = await fetch_counts(conn)
                newly_matched = after_matched - already_matched
                print(f"\nNewly matched       : {newly_matched}")
                print(f"Remaining unmatched : {after_unmatched}")
                unmatched = after_unmatched

        total_matched = total - unmatched
        pct = (total_matched / total * 100) if total else 0.0
        print(f"\nMatch rate          : {pct:.1f}%  ({total_matched}/{total})")

        exit_code = compute_exit_code(total, total_matched)
        if exit_code == 0:
            print("Result              : OK (>=70% matched)")
        else:
            print("Result              : WARN (<70% matched)")

        return exit_code

    finally:
        await conn.close()


if __name__ == "__main__":
    args = build_argparser().parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
