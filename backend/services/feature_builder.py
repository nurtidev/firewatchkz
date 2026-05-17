"""
services/feature_builder.py — Pure-Python feature computation helpers.

FeatureBuilder contains static methods for features that do NOT require a DB
connection, making them unit-testable in isolation.
"""
from __future__ import annotations

import datetime
from typing import Optional


class FeatureBuilder:
    """Stateless helper class for computing building risk features."""

    @staticmethod
    def compute_population_estimate(
        floors_above: Optional[float],
        total_area_sqm: Optional[float],
    ) -> Optional[float]:
        """
        Rough population estimate: floors_above * total_area_sqm * 0.05.

        Returns None if either input is None.
        Returns the result rounded to 0 decimal places (as a float).
        """
        if floors_above is None or total_area_sqm is None:
            return None
        return round(floors_above * total_area_sqm * 0.05, 0)

    @staticmethod
    def compute_age_years(year_built: Optional[int]) -> Optional[int]:
        """
        Compute building age in years from year_built.

        Returns None if year_built is None.
        """
        if year_built is None:
            return None
        current_year = datetime.datetime.now().year
        return current_year - year_built
