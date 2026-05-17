"""
workers/weather.py — Celery task to fetch hourly weather data for Astana.

fetch_weather  — calls OpenWeatherMap API, inserts row into weather_history (H-3)
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from celery_app import celery_app

logger = logging.getLogger(__name__)

# Astana city center coordinates
ASTANA_LAT = 51.1801
ASTANA_LON = 71.4460
H3_RESOLUTION = 8

OWM_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sync_db_conn():
    """Return a psycopg (sync) connection using DATABASE_URL env var."""
    import psycopg  # noqa: PLC0415 — optional at import time

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://firewatch:firewatch_dev@localhost:5432/firewatch",
    )
    # psycopg uses postgresql:// scheme (no +asyncpg driver qualifier)
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
    return psycopg.connect(sync_url)


def _compute_h3_cell(lat: float, lon: float, resolution: int) -> str:
    """Compute H3 cell for given coordinates. Returns 'h3_unavailable' if h3 not installed."""
    try:
        import h3  # noqa: PLC0415

        return h3.latlng_to_cell(lat, lon, resolution)
    except ImportError:
        logger.warning("h3 package not installed — using fallback h3_cell value")
        return "h3_unavailable"
    except Exception as exc:
        logger.warning("h3 cell computation failed: %s — using fallback", exc)
        return "h3_unavailable"


def _fetch_owm_data(api_key: str) -> Dict[str, Any]:
    """
    Fetch current weather from OpenWeatherMap for Astana.

    Tries `requests` first; falls back to `urllib.request`.
    Returns parsed JSON dict.
    """
    params = {
        "lat": ASTANA_LAT,
        "lon": ASTANA_LON,
        "appid": api_key,
        "units": "metric",
    }

    # Build query string manually for urllib fallback
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{OWM_BASE_URL}?{query_string}"

    # --- attempt 1: requests ---
    try:
        import requests  # noqa: PLC0415

        response = requests.get(OWM_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except ImportError:
        logger.debug("requests not installed — falling back to urllib.request")

    # --- attempt 2: urllib.request ---
    import json  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _truncate_to_hour(dt: datetime) -> datetime:
    """Truncate a datetime to the current hour (zero out minutes, seconds, microseconds)."""
    return dt.replace(minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="workers.weather.fetch_weather",
    max_retries=0,  # periodic task — do not retry; next run is in 1 hour
)
def fetch_weather(self) -> Dict[str, Any]:
    """
    Fetch current weather for Astana from OpenWeatherMap and store in weather_history.

    Returns a dict with the result or {"skipped": True} if the API key is missing.
    Never raises an exception — all errors are caught and returned as error dicts.
    """
    try:
        api_key = os.getenv("OPENWEATHERMAP_API_KEY", "").strip()
        if not api_key:
            logger.warning(
                "fetch_weather: OPENWEATHERMAP_API_KEY not set — skipping task"
            )
            return {"skipped": True, "reason": "no_api_key"}

        ts = _truncate_to_hour(datetime.now(timezone.utc))
        h3_cell = _compute_h3_cell(ASTANA_LAT, ASTANA_LON, H3_RESOLUTION)

        logger.info(
            "fetch_weather: fetching OWM data for Astana, ts=%s, h3_cell=%s",
            ts.isoformat(),
            h3_cell,
        )

        data = _fetch_owm_data(api_key)

        # Extract fields from OWM response
        main = data.get("main", {})
        wind = data.get("wind", {})
        rain = data.get("rain", {})

        temp_c = main.get("temp")
        wind_ms = wind.get("speed")
        humidity_pct = main.get("humidity")
        # OWM rain.1h is mm in the last hour
        precipitation_mm = rain.get("1h", 0.0)

        logger.info(
            "fetch_weather: OWM response — temp=%.1f°C, wind=%.1f m/s, humidity=%s%%, rain=%.2f mm",
            temp_c or 0,
            wind_ms or 0,
            humidity_pct or 0,
            precipitation_mm or 0,
        )

        conn = _sync_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO weather_history
                        (ts, h3_cell, temp_c, wind_ms, humidity_pct, precipitation_mm)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ts, h3_cell) DO NOTHING
                    """,
                    (ts, h3_cell, temp_c, wind_ms, humidity_pct, precipitation_mm),
                )
            conn.commit()
        finally:
            conn.close()

        logger.info("fetch_weather: row inserted (or skipped on conflict) for ts=%s", ts.isoformat())

        return {
            "ts": ts.isoformat(),
            "h3_cell": h3_cell,
            "temp_c": temp_c,
            "wind_ms": wind_ms,
            "humidity_pct": humidity_pct,
            "precipitation_mm": precipitation_mm,
        }

    except Exception as exc:
        logger.error("fetch_weather: unexpected error — %s", exc, exc_info=True)
        return {"error": str(exc)}
