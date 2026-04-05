from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


_FORECAST_CACHE: dict[str, dict] = {}
_CACHE_TTL = timedelta(hours=24)
_Z_SCORE_80 = 1.2815515655446004


class Forecaster:
    def generate_forecast(self, city: str, monthly_counts: pd.DataFrame, months: int) -> dict:
        cache_key = f"{city}:{months}"
        cached_entry = _FORECAST_CACHE.get(cache_key)
        now = datetime.utcnow()

        if cached_entry and now - cached_entry["timestamp"] < _CACHE_TTL:
            return cached_entry["payload"]

        series = monthly_counts.copy().sort_values("year_month").reset_index(drop=True)
        indexed_series = series.set_index("year_month")["count"].astype(float)

        model = ExponentialSmoothing(
            indexed_series,
            trend="add",
            seasonal="add",
            seasonal_periods=12,
        )
        fit = model.fit(optimized=True)

        fitted_values = fit.fittedvalues
        actual_values = indexed_series
        sse = float(((actual_values - fitted_values) ** 2).sum())
        sst = float(((actual_values - actual_values.mean()) ** 2).sum())
        r_squared = 1.0 if sst == 0 else max(0.0, 1 - (sse / sst))

        forecast_values = fit.forecast(months)
        residuals = actual_values - fitted_values
        residual_std = float(residuals.std(ddof=1)) if len(residuals) > 1 else 0.0

        historical = [
            {"period": str(period), "actual": int(round(value))}
            for period, value in actual_values.items()
        ]

        forecast: list[dict] = []
        for step, (period, value) in enumerate(forecast_values.items(), start=1):
            interval_width = _Z_SCORE_80 * residual_std * np.sqrt(step)
            predicted = int(round(value))
            lower_80 = max(0, int(round(value - interval_width)))
            upper_80 = max(predicted, int(round(value + interval_width)))
            forecast.append(
                {
                    "period": str(period),
                    "predicted": predicted,
                    "lower_80": lower_80,
                    "upper_80": upper_80,
                }
            )

        payload = {
            "city": city,
            "months": months,
            "model": "Holt-Winters ETS",
            "r_squared": round(r_squared, 2),
            "historical": historical,
            "forecast": forecast,
        }
        _FORECAST_CACHE[cache_key] = {"timestamp": now, "payload": payload}
        return payload


forecaster = Forecaster()
