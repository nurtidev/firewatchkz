"""
services/dynamic_modifier.py — Rules-based dynamic fire risk modifier.

compute_modifier(weather, now) -> ModifierResult

ModifierResult has:
  - multiplier: float — final clamped multiplier [0.3, 3.0]
  - breakdown: List[dict] — list of {factor, contribution, description, applied} for UI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Inputs / Outputs
# ---------------------------------------------------------------------------


@dataclass
class WeatherInput:
    temp_c: Optional[float] = None
    wind_ms: Optional[float] = None
    humidity_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None


@dataclass
class ModifierResult:
    multiplier: float                # clamped to [0.3, 3.0]
    breakdown: List[Dict]            # [{factor, raw_factor, description, applied}]


# ---------------------------------------------------------------------------
# Kazakhstan public holidays (hardcoded — no external API calls)
# ---------------------------------------------------------------------------

# Each entry is (month, day) or (month, day_start, day_end) for ranges.
_HOLIDAY_RANGES: List[tuple] = [
    (1, 1, 2),    # New Year: Jan 1–2
    (1, 7, 7),    # Orthodox Christmas: Jan 7
    (3, 8, 8),    # International Women's Day: Mar 8
    (3, 21, 23),  # Nauryz: Mar 21–23
    (5, 1, 1),    # Kazakhstan People's Day: May 1
    (5, 7, 7),    # Defender of the Fatherland Day: May 7
    (5, 9, 9),    # Victory Day: May 9
    (7, 6, 6),    # Capital City Day: Jul 6
    (8, 30, 30),  # Constitution Day: Aug 30
    (10, 25, 25), # Republic Day: Oct 25
    (12, 16, 17), # Independence Day: Dec 16–17
]


def is_major_holiday(dt: datetime) -> bool:
    """Return True if *dt* falls on a Kazakhstan major public holiday."""
    m, d = dt.month, dt.day
    for entry in _HOLIDAY_RANGES:
        month, day_start, day_end = entry
        if m == month and day_start <= d <= day_end:
            return True
    return False


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def is_friday_or_saturday_evening(dt: datetime) -> bool:
    """Return True if *dt* is a Friday or Saturday at or after 18:00."""
    return dt.weekday() in (4, 5) and dt.hour >= 18


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

_MIN_MULT = 0.3
_MAX_MULT = 3.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_modifier(weather: WeatherInput, now: datetime) -> ModifierResult:
    """Apply all risk rules and return a clamped multiplier with full breakdown.

    Rules are applied multiplicatively.  Each rule that fires contributes an
    entry to *breakdown* regardless of whether it actually changed *mult* (the
    ``applied`` field records this).
    """
    mult = 1.0
    breakdown: List[Dict] = []

    def _record(
        factor: str,
        raw_factor: float,
        description: str,
        applied: bool,
    ) -> None:
        breakdown.append(
            {
                "factor": factor,
                "raw_factor": raw_factor,
                "description": description,
                "applied": applied,
            }
        )

    # ------------------------------------------------------------------
    # Heating season — sub-zero temperatures increase risk of electrical
    # failures and open-flame heating.
    # ------------------------------------------------------------------
    temp_c = weather.temp_c

    cold_base_applied = False
    cold_severe_applied = False

    if temp_c is not None and temp_c < 0:
        mult *= 1.30
        cold_base_applied = True

    if temp_c is not None and temp_c < -20:
        mult *= 1.15
        cold_severe_applied = True

    _record(
        factor="cold_below_zero",
        raw_factor=1.30,
        description="Отопительный сезон (температура ниже 0°C): повышенная нагрузка на системы отопления",
        applied=cold_base_applied,
    )
    _record(
        factor="cold_severe",
        raw_factor=1.15,
        description="Сильный мороз (ниже -20°C): дополнительный риск отказа оборудования",
        applied=cold_severe_applied,
    )

    # ------------------------------------------------------------------
    # Wind — accelerates fire spread.
    # ------------------------------------------------------------------
    wind_ms = weather.wind_ms

    wind_base_applied = False
    wind_strong_applied = False

    if wind_ms is not None and wind_ms > 10:
        mult *= 1.20
        wind_base_applied = True

    if wind_ms is not None and wind_ms > 15:
        mult *= 1.40
        wind_strong_applied = True

    _record(
        factor="wind_moderate",
        raw_factor=1.20,
        description="Ветер >10 м/с: ускоренное распространение огня",
        applied=wind_base_applied,
    )
    _record(
        factor="wind_strong",
        raw_factor=1.40,
        description="Сильный ветер >15 м/с: высокий риск распространения пожара",
        applied=wind_strong_applied,
    )

    # ------------------------------------------------------------------
    # Hot and dry — increases ignition probability.
    # ------------------------------------------------------------------
    humidity_pct = weather.humidity_pct

    hot_dry_applied = False
    if (
        temp_c is not None
        and humidity_pct is not None
        and temp_c > 30
        and humidity_pct < 30
    ):
        mult *= 1.25
        hot_dry_applied = True

    _record(
        factor="hot_dry",
        raw_factor=1.25,
        description="Жаркая сухая погода (>30°C и влажность <30%): высокая пожарная опасность",
        applied=hot_dry_applied,
    )

    # ------------------------------------------------------------------
    # Public holidays — more gatherings, often fireworks / open flames.
    # ------------------------------------------------------------------
    holiday_applied = is_major_holiday(now)
    if holiday_applied:
        mult *= 1.35

    _record(
        factor="major_holiday",
        raw_factor=1.35,
        description="Государственный праздник Казахстана: повышенная активность населения и использование пиротехники",
        applied=holiday_applied,
    )

    # ------------------------------------------------------------------
    # Friday / Saturday evening — peak social activity.
    # ------------------------------------------------------------------
    fri_sat_applied = is_friday_or_saturday_evening(now)
    if fri_sat_applied:
        mult *= 1.15

    _record(
        factor="friday_saturday_evening",
        raw_factor=1.15,
        description="Пятница/суббота вечер (≥18:00): повышенная активность населения",
        applied=fri_sat_applied,
    )

    # ------------------------------------------------------------------
    # Clamp and return.
    # ------------------------------------------------------------------
    clamped = _clamp(mult, _MIN_MULT, _MAX_MULT)

    return ModifierResult(multiplier=clamped, breakdown=breakdown)
