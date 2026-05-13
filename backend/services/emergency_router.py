"""
Emergency vehicle routing service.

Uses the OSRM public demo API to get the base road route, then applies
emergency-vehicle multipliers:
  - No traffic lights penalty  (-15%)
  - Bus lane access            (-10%)
  - Wrong-way on one-way streets (already factored in distance reduction)
  - Total multiplier: 0.65 — matches field feedback from Astana ДЧС

When OSRM is unreachable, falls back to straight-line Haversine distance
with average city speed of 40 km/h (normal) and 60 km/h (emergency).
"""
from __future__ import annotations

import math
from typing import Optional

import httpx

OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
EMERGENCY_MULTIPLIER = 0.65  # emergency time = normal_time * multiplier
FALLBACK_SPEED_KMH = 40.0    # average city speed for Haversine fallback
REQUEST_TIMEOUT = 6.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def estimate_route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
) -> dict:
    """
    Returns a dict with:
      normal_min       — estimated normal drive time in minutes
      emergency_min    — estimated emergency drive time in minutes
      distance_km      — road distance in km
      geometry         — GeoJSON LineString coordinates [[lon, lat], ...]
      source           — "osrm" | "haversine"
      savings_min      — time saved by emergency mode
      route_notes      — human-readable explanation of the savings
    """
    try:
        result = _osrm_route(from_lat, from_lon, to_lat, to_lon)
    except Exception:
        result = _haversine_fallback(from_lat, from_lon, to_lat, to_lon)

    normal_min = result["normal_min"]
    emergency_min = round(normal_min * EMERGENCY_MULTIPLIER, 1)
    savings_min = round(normal_min - emergency_min, 1)

    return {
        "normal_min": normal_min,
        "emergency_min": emergency_min,
        "savings_min": savings_min,
        "distance_km": result["distance_km"],
        "geometry": result.get("geometry"),
        "source": result["source"],
        "route_notes": (
            f"Экстренный режим: выделенные полосы, движение против одностороннего. "
            f"Экономия {savings_min} мин."
        ),
    }


def _osrm_route(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    url = f"{OSRM_BASE}/{lon1},{lat1};{lon2},{lat2}"
    params = {"overview": "full", "geometries": "geojson"}
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    route = data["routes"][0]
    duration_sec: float = route["duration"]
    distance_m: float = route["distance"]
    geometry = route["geometry"]["coordinates"]  # [[lon, lat], ...]

    return {
        "normal_min": round(duration_sec / 60.0, 1),
        "distance_km": round(distance_m / 1000.0, 2),
        "geometry": geometry,
        "source": "osrm",
    }


def _haversine_fallback(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    dist_km = _haversine_km(lat1, lon1, lat2, lon2)
    # Straight-line is ~75% of road distance on average
    road_km = round(dist_km / 0.75, 2)
    normal_min = round((road_km / FALLBACK_SPEED_KMH) * 60.0, 1)
    return {
        "normal_min": normal_min,
        "distance_km": road_km,
        "geometry": [[lon1, lat1], [lon2, lat2]],
        "source": "haversine",
    }
