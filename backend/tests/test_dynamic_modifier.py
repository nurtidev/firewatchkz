"""
tests/test_dynamic_modifier.py — Unit tests for the dynamic fire risk modifier.

Run:
    cd backend && python3 -m pytest tests/test_dynamic_modifier.py -v
"""

from datetime import datetime, timezone

import pytest

from services.dynamic_modifier import (
    WeatherInput,
    ModifierResult,
    compute_modifier,
    is_major_holiday,
    is_friday_or_saturday_evening,
)

# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

# Jan 1 2026 at 20:00 UTC — New Year's Day evening (holiday)
dt_new_year_evening = datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)

# Tuesday 2026-06-02 at 12:00 UTC — ordinary summer weekday, no holiday
dt_tuesday_noon = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Acceptance-criteria tests (from spec)
# ---------------------------------------------------------------------------


def test_extreme_cold_wind_holiday_gives_high_multiplier():
    """
    temp=-25, wind=12, is New Year's Day (holiday=True).

    Expected factors applied:
      cold_below_zero : ×1.30
      cold_severe     : ×1.15
      wind_moderate   : ×1.20
      major_holiday   : ×1.35
    Product = 1.0 * 1.30 * 1.15 * 1.20 * 1.35 ≈ 2.71  (< 3.0, no clamp)
    Requirement: multiplier >= 2.0
    """
    result = compute_modifier(
        WeatherInput(temp_c=-25, wind_ms=12),
        dt_new_year_evening,
    )
    assert result.multiplier >= 2.0, f"Expected >= 2.0, got {result.multiplier:.4f}"


def test_summer_weekday_normal_weather():
    """
    temp=22, wind=3, Tuesday noon, no holiday → no factors apply → ≈ 1.0
    """
    result = compute_modifier(
        WeatherInput(temp_c=22, wind_ms=3, humidity_pct=60),
        dt_tuesday_noon,
    )
    assert 0.9 <= result.multiplier <= 1.2, (
        f"Expected 0.9-1.2 for normal summer weekday, got {result.multiplier:.4f}"
    )


def test_hot_dry_weather_increases_risk():
    """temp=32, humidity=25 → hot_dry factor (×1.25) should apply."""
    result = compute_modifier(
        WeatherInput(temp_c=32, wind_ms=5, humidity_pct=25),
        dt_tuesday_noon,
    )
    assert result.multiplier > 1.2, (
        f"Expected > 1.2 for hot/dry weather, got {result.multiplier:.4f}"
    )


def test_clamp_upper_bound():
    """Pathological case: all cold + strong wind + holiday → must not exceed 3.0."""
    result = compute_modifier(
        WeatherInput(temp_c=-30, wind_ms=20, humidity_pct=20),
        dt_new_year_evening,
    )
    assert result.multiplier <= 3.0, (
        f"Multiplier exceeded 3.0 upper bound: {result.multiplier:.4f}"
    )


def test_clamp_lower_bound():
    """Multiplier must never go below 0.3 (even with no risk factors)."""
    result = compute_modifier(
        WeatherInput(temp_c=20, wind_ms=2, humidity_pct=70),
        dt_tuesday_noon,
    )
    assert result.multiplier >= 0.3, (
        f"Multiplier fell below 0.3 lower bound: {result.multiplier:.4f}"
    )


def test_breakdown_is_list_of_dicts():
    """breakdown must be a list of dicts with at least 'factor' and 'description' keys."""
    result = compute_modifier(
        WeatherInput(temp_c=-25, wind_ms=12),
        dt_tuesday_noon,
    )
    assert isinstance(result.breakdown, list), "breakdown should be a list"
    assert len(result.breakdown) > 0, "breakdown should not be empty"
    for entry in result.breakdown:
        assert "factor" in entry, f"Missing 'factor' key in breakdown entry: {entry}"
        assert "description" in entry, (
            f"Missing 'description' key in breakdown entry: {entry}"
        )


def test_friday_evening_applies_factor():
    """Friday evening should produce a higher multiplier than the same Friday morning."""
    dt_friday_evening = datetime(2026, 5, 15, 20, 0, tzinfo=timezone.utc)  # Friday
    dt_friday_morning = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)

    result_evening = compute_modifier(
        WeatherInput(temp_c=20, wind_ms=3),
        dt_friday_evening,
    )
    result_morning = compute_modifier(
        WeatherInput(temp_c=20, wind_ms=3),
        dt_friday_morning,
    )
    assert result_evening.multiplier > result_morning.multiplier, (
        f"Friday evening ({result_evening.multiplier:.4f}) should exceed "
        f"Friday morning ({result_morning.multiplier:.4f})"
    )


# ---------------------------------------------------------------------------
# is_major_holiday tests
# ---------------------------------------------------------------------------


def test_is_major_holiday_new_year():
    assert is_major_holiday(datetime(2026, 1, 1, 12, 0)) is True
    assert is_major_holiday(datetime(2026, 1, 2, 12, 0)) is True   # still New Year
    assert is_major_holiday(datetime(2026, 1, 15, 12, 0)) is False


def test_nauryz_is_holiday():
    assert is_major_holiday(datetime(2026, 3, 21, 12, 0)) is True
    assert is_major_holiday(datetime(2026, 3, 22, 12, 0)) is True
    assert is_major_holiday(datetime(2026, 3, 23, 12, 0)) is True
    assert is_major_holiday(datetime(2026, 3, 20, 12, 0)) is False  # day before


def test_independence_day_is_holiday():
    assert is_major_holiday(datetime(2026, 12, 16, 12, 0)) is True
    assert is_major_holiday(datetime(2026, 12, 17, 12, 0)) is True
    assert is_major_holiday(datetime(2026, 12, 15, 12, 0)) is False  # day before


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_breakdown_applied_flags():
    """All factors that should fire on a cold-wind-holiday day must have applied=True."""
    result = compute_modifier(
        WeatherInput(temp_c=-25, wind_ms=12),
        dt_new_year_evening,
    )
    applied_factors = {e["factor"] for e in result.breakdown if e["applied"]}
    assert "cold_below_zero" in applied_factors
    assert "cold_severe" in applied_factors
    assert "wind_moderate" in applied_factors
    assert "major_holiday" in applied_factors


def test_breakdown_unapplied_flags():
    """On a normal summer day, risk factors should be marked as not applied."""
    result = compute_modifier(
        WeatherInput(temp_c=22, wind_ms=3, humidity_pct=60),
        dt_tuesday_noon,
    )
    unapplied = {e["factor"] for e in result.breakdown if not e["applied"]}
    assert "cold_below_zero" in unapplied
    assert "cold_severe" in unapplied
    assert "wind_moderate" in unapplied
    assert "major_holiday" in unapplied
    assert "friday_saturday_evening" in unapplied


def test_wind_above_15_applies_both_wind_factors():
    """Wind > 15 m/s should apply both wind_moderate (×1.20) and wind_strong (×1.40)."""
    result = compute_modifier(
        WeatherInput(temp_c=15, wind_ms=20),
        dt_tuesday_noon,
    )
    applied = {e["factor"] for e in result.breakdown if e["applied"]}
    assert "wind_moderate" in applied
    assert "wind_strong" in applied
    # Baseline ×1.20 ×1.40 = 1.68
    assert result.multiplier > 1.6, f"Expected > 1.6, got {result.multiplier:.4f}"


def test_none_weather_values_ignored():
    """None weather values should not raise and should not apply any weather factor."""
    result = compute_modifier(WeatherInput(), dt_tuesday_noon)
    assert 0.3 <= result.multiplier <= 3.0
    applied = {e["factor"] for e in result.breakdown if e["applied"]}
    assert "cold_below_zero" not in applied
    assert "wind_moderate" not in applied
    assert "hot_dry" not in applied


def test_result_is_modifier_result_instance():
    result = compute_modifier(WeatherInput(temp_c=10, wind_ms=5), dt_tuesday_noon)
    assert isinstance(result, ModifierResult)


def test_breakdown_raw_factor_present():
    """Every breakdown entry must include a numeric raw_factor."""
    result = compute_modifier(WeatherInput(temp_c=-25, wind_ms=12), dt_new_year_evening)
    for entry in result.breakdown:
        assert "raw_factor" in entry, f"Missing raw_factor in: {entry}"
        assert isinstance(entry["raw_factor"], (int, float)), (
            f"raw_factor should be numeric, got {type(entry['raw_factor'])}"
        )


def test_multiplier_exact_cold_wind_holiday():
    """
    Verify expected product for temp=-25, wind=12, New Year's evening (no hot/dry,
    no Friday/Saturday — Jan 1 2026 is a Thursday).

    Factors: cold_below_zero ×1.30, cold_severe ×1.15, wind_moderate ×1.20,
             major_holiday ×1.35
    Product = 1.30 × 1.15 × 1.20 × 1.35 = 2.7081
    """
    result = compute_modifier(
        WeatherInput(temp_c=-25, wind_ms=12),
        dt_new_year_evening,
    )
    expected = 1.30 * 1.15 * 1.20 * 1.35
    assert abs(result.multiplier - expected) < 0.001, (
        f"Expected {expected:.4f}, got {result.multiplier:.4f}"
    )


def test_all_factors_max_clamp():
    """
    All factors fire at once: cold ×1.30 ×1.15, strong wind ×1.20 ×1.40,
    holiday ×1.35, friday evening ×1.15.
    Raw = 1.30 × 1.15 × 1.20 × 1.40 × 1.35 × 1.15 ≈ 4.49 → clamped to 3.0
    """
    # Jan 2 2026 is a Friday
    dt_friday_new_year = datetime(2026, 1, 2, 20, 0, tzinfo=timezone.utc)
    result = compute_modifier(
        WeatherInput(temp_c=-30, wind_ms=20, humidity_pct=20),
        dt_friday_new_year,
    )
    assert result.multiplier == 3.0, (
        f"Expected clamped 3.0, got {result.multiplier:.4f}"
    )


def test_is_friday_or_saturday_evening_true():
    # Friday 20:00
    assert is_friday_or_saturday_evening(datetime(2026, 5, 15, 20, 0)) is True
    # Saturday 18:00
    assert is_friday_or_saturday_evening(datetime(2026, 5, 16, 18, 0)) is True


def test_is_friday_or_saturday_evening_false():
    # Friday morning
    assert is_friday_or_saturday_evening(datetime(2026, 5, 15, 9, 0)) is False
    # Sunday evening
    assert is_friday_or_saturday_evening(datetime(2026, 5, 17, 20, 0)) is False
    # Monday evening
    assert is_friday_or_saturday_evening(datetime(2026, 5, 18, 20, 0)) is False
