"""
tests/test_match_incidents.py — Unit tests for H-2 match_incidents_to_buildings.

Tests pure helper functions only — no live DB required.
"""
import argparse
import sys

import pytest


# ---------------------------------------------------------------------------
# Import the helpers under test
# ---------------------------------------------------------------------------

from scripts.match_incidents_to_buildings import (
    MATCH_SQL,
    build_argparser,
    compute_exit_code,
)


# ---------------------------------------------------------------------------
# compute_exit_code
# ---------------------------------------------------------------------------


def test_exit_code_zero_when_all_matched():
    assert compute_exit_code(total=100, matched=100) == 0


def test_exit_code_zero_at_exactly_70_pct():
    assert compute_exit_code(total=100, matched=70) == 0


def test_exit_code_one_below_70_pct():
    assert compute_exit_code(total=100, matched=69) == 1


def test_exit_code_zero_when_nothing_to_match():
    # Empty table — consider success
    assert compute_exit_code(total=0, matched=0) == 0


def test_exit_code_one_when_none_matched():
    assert compute_exit_code(total=50, matched=0) == 1


# ---------------------------------------------------------------------------
# MATCH_SQL sanity
# ---------------------------------------------------------------------------


def test_match_sql_is_idempotent_guard():
    assert "building_id IS NULL" in MATCH_SQL


def test_match_sql_uses_30m_radius():
    assert "30" in MATCH_SQL


def test_match_sql_uses_geography_cast():
    assert "::geography" in MATCH_SQL


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def test_argparser_dry_run_defaults_false():
    parser = build_argparser()
    args = parser.parse_args([])
    assert args.dry_run is False


def test_argparser_dry_run_flag():
    parser = build_argparser()
    args = parser.parse_args(["--dry-run"])
    assert args.dry_run is True
