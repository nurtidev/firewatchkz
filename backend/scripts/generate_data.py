from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np


DISTRICTS = {
    "Есіл": {
        "lat_range": (51.15, 51.22),
        "lon_range": (71.40, 71.55),
        "weight": 0.24,
        "building_weights": {
            "residential": 0.34,
            "commercial": 0.33,
            "industrial": 0.08,
            "construction": 0.18,
            "other": 0.07,
        },
        "cause_weights": {
            "electrical": 0.40,
            "open_flame": 0.24,
            "arson": 0.08,
            "children": 0.05,
            "other": 0.23,
        },
        "severity_weights": {
            "low": 0.51,
            "medium": 0.31,
            "high": 0.14,
            "critical": 0.04,
        },
    },
    "Алматы": {
        "lat_range": (51.17, 51.25),
        "lon_range": (71.28, 71.42),
        "weight": 0.21,
        "building_weights": {
            "residential": 0.43,
            "commercial": 0.22,
            "industrial": 0.10,
            "construction": 0.15,
            "other": 0.10,
        },
        "cause_weights": {
            "electrical": 0.30,
            "open_flame": 0.26,
            "arson": 0.10,
            "children": 0.12,
            "other": 0.22,
        },
        "severity_weights": {
            "low": 0.56,
            "medium": 0.27,
            "high": 0.13,
            "critical": 0.04,
        },
    },
    "Байқоңыр": {
        "lat_range": (51.10, 51.18),
        "lon_range": (71.35, 71.45),
        "weight": 0.18,
        "building_weights": {
            "residential": 0.28,
            "commercial": 0.18,
            "industrial": 0.31,
            "construction": 0.13,
            "other": 0.10,
        },
        "cause_weights": {
            "electrical": 0.29,
            "open_flame": 0.24,
            "arson": 0.11,
            "children": 0.06,
            "other": 0.30,
        },
        "severity_weights": {
            "low": 0.38,
            "medium": 0.31,
            "high": 0.21,
            "critical": 0.10,
        },
    },
    "Сарыарқа": {
        "lat_range": (51.18, 51.28),
        "lon_range": (71.42, 71.58),
        "weight": 0.22,
        "building_weights": {
            "residential": 0.41,
            "commercial": 0.25,
            "industrial": 0.09,
            "construction": 0.15,
            "other": 0.10,
        },
        "cause_weights": {
            "electrical": 0.28,
            "open_flame": 0.28,
            "arson": 0.10,
            "children": 0.09,
            "other": 0.25,
        },
        "severity_weights": {
            "low": 0.54,
            "medium": 0.29,
            "high": 0.13,
            "critical": 0.04,
        },
    },
    "Нұра": {
        "lat_range": (51.08, 51.16),
        "lon_range": (71.45, 71.58),
        "weight": 0.15,
        "building_weights": {
            "residential": 0.39,
            "commercial": 0.19,
            "industrial": 0.12,
            "construction": 0.20,
            "other": 0.10,
        },
        "cause_weights": {
            "electrical": 0.27,
            "open_flame": 0.27,
            "arson": 0.08,
            "children": 0.08,
            "other": 0.30,
        },
        "severity_weights": {
            "low": 0.52,
            "medium": 0.30,
            "high": 0.14,
            "critical": 0.04,
        },
    },
}

SEVERITY_DAMAGE_RANGES = {
    "low": (50_000, 500_000),
    "medium": (500_000, 5_000_000),
    "high": (5_000_000, 50_000_000),
    "critical": (50_000_000, 500_000_000),
}

CASUALTY_VALUES = np.arange(0, 11)
CASUALTY_WEIGHTS = np.array([0.63, 0.17, 0.08, 0.04, 0.025, 0.018, 0.012, 0.009, 0.007, 0.005, 0.004])
CASUALTY_WEIGHTS = CASUALTY_WEIGHTS / CASUALTY_WEIGHTS.sum()


@dataclass(frozen=True)
class IncidentRecord:
    id: str
    date: str
    city: str
    district: str
    building_type: str
    cause: str
    severity: str
    casualties: int
    damage_tenge: int
    lat: float
    lon: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic fire incident data.")
    parser.add_argument("--city", required=True, help="City slug, currently supports only 'astana'.")
    parser.add_argument("--years", type=int, default=3, help="Number of years of history to generate.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible output.")
    return parser.parse_args()


def month_weight(month: int) -> float:
    if month in {1, 2, 5, 6}:
        return 2.0
    return 1.0


def date_pool(years: int) -> list[date]:
    end_date = date.today()
    start_date = end_date - timedelta(days=years * 365 - 1)
    total_days = (end_date - start_date).days + 1
    return [start_date + timedelta(days=offset) for offset in range(total_days)]


def weighted_dates(dates: list[date]) -> np.ndarray:
    weights = np.array([month_weight(current.month) for current in dates], dtype=float)
    weights /= weights.sum()
    return weights


def target_incident_count(years: int, rng: np.random.Generator) -> int:
    base = rng.integers(267, 401)
    return int(base * years)


def choose_weighted(rng: np.random.Generator, options: dict[str, float]) -> str:
    values = list(options.keys())
    weights = np.array(list(options.values()), dtype=float)
    weights /= weights.sum()
    return str(rng.choice(values, p=weights))


def choose_building_type(rng: np.random.Generator, district: str, incident_date: date) -> str:
    weights = DISTRICTS[district]["building_weights"].copy()
    if incident_date.weekday() >= 5:
        weights["residential"] += 0.20
        total = sum(weights.values())
        weights = {key: value / total for key, value in weights.items()}
    return choose_weighted(rng, weights)


def choose_cause(rng: np.random.Generator, district: str, building_type: str, incident_date: date) -> str:
    weights = DISTRICTS[district]["cause_weights"].copy()
    if building_type == "residential" and incident_date.month in {1, 2}:
        weights["open_flame"] += 0.05
        weights["children"] += 0.03
    if building_type == "commercial":
        weights["electrical"] += 0.04
    return choose_weighted(rng, weights)


def choose_severity(rng: np.random.Generator, district: str, building_type: str, cause: str) -> str:
    weights = DISTRICTS[district]["severity_weights"].copy()
    if building_type == "industrial":
        weights["high"] += 0.06
        weights["critical"] += 0.04
    if cause == "arson":
        weights["medium"] += 0.03
        weights["high"] += 0.03
    return choose_weighted(rng, weights)


def damage_for_severity(rng: np.random.Generator, severity: str) -> int:
    low, high = SEVERITY_DAMAGE_RANGES[severity]
    return int(rng.integers(low, high + 1))


def incident_coordinates(rng: np.random.Generator, district: str) -> tuple[float, float]:
    lat_low, lat_high = DISTRICTS[district]["lat_range"]
    lon_low, lon_high = DISTRICTS[district]["lon_range"]
    lat = round(float(rng.uniform(lat_low, lat_high)), 6)
    lon = round(float(rng.uniform(lon_low, lon_high)), 6)
    return lat, lon


def generate_incidents(city: str, years: int, seed: int) -> list[IncidentRecord]:
    if city != "astana":
        raise ValueError("Only 'astana' is supported for synthetic generation.")
    if years < 1:
        raise ValueError("--years must be at least 1.")

    rng = np.random.default_rng(seed)
    all_dates = date_pool(years)
    incident_count = target_incident_count(years, rng)
    sampled_dates = rng.choice(all_dates, size=incident_count, p=weighted_dates(all_dates), replace=True)

    district_names = list(DISTRICTS.keys())
    district_weights = np.array([DISTRICTS[name]["weight"] for name in district_names], dtype=float)
    district_weights /= district_weights.sum()

    records: list[IncidentRecord] = []
    for index, sampled_date in enumerate(sorted(sampled_dates), start=1):
        incident_date = sampled_date.item() if hasattr(sampled_date, "item") else sampled_date
        district = str(rng.choice(district_names, p=district_weights))
        building_type = choose_building_type(rng, district, incident_date)
        cause = choose_cause(rng, district, building_type, incident_date)
        severity = choose_severity(rng, district, building_type, cause)
        casualties = int(rng.choice(CASUALTY_VALUES, p=CASUALTY_WEIGHTS))
        damage_tenge = damage_for_severity(rng, severity)
        lat, lon = incident_coordinates(rng, district)

        records.append(
            IncidentRecord(
                id=f"ast-{incident_date:%Y%m%d}-{index:04d}",
                date=incident_date.isoformat(),
                city=city,
                district=district,
                building_type=building_type,
                cause=cause,
                severity=severity,
                casualties=casualties,
                damage_tenge=damage_tenge,
                lat=lat,
                lon=lon,
            )
        )

    return records


def write_csv(records: list[IncidentRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "date",
        "city",
        "district",
        "building_type",
        "cause",
        "severity",
        "casualties",
        "damage_tenge",
        "lat",
        "lon",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.__dict__)


def summarize(records: list[IncidentRecord]) -> dict[str, Any]:
    by_month: dict[str, int] = {}
    for record in records:
        month_key = record.date[:7]
        by_month[month_key] = by_month.get(month_key, 0) + 1
    return {
        "rows": len(records),
        "first_date": records[0].date if records else None,
        "last_date": records[-1].date if records else None,
        "months": len(by_month),
    }


def main() -> None:
    args = parse_args()
    output_path = Path(args.output).expanduser()
    records = generate_incidents(city=args.city.lower(), years=args.years, seed=args.seed)
    write_csv(records, output_path)
    summary = summarize(records)
    print(
        f"Generated {summary['rows']} incidents for {args.city} "
        f"from {summary['first_date']} to {summary['last_date']} -> {output_path}"
    )


if __name__ == "__main__":
    main()
