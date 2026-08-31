"""Assign HIGH / MEDIUM / LOW confidence to a distribution opportunity."""

from __future__ import annotations

import pandas as pd

from backend.agents.distribution.models import Confidence, DistributionConfig
from backend.agents.distribution.outliers import mad_outlier_mask


def coefficient_of_variation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    series = pd.Series(values, dtype="float64")
    mean = float(series.mean())
    if mean == 0:
        return None
    return float(series.std(ddof=0) / abs(mean))


def assign_confidence(
    *,
    n_periods: int,
    current_stores: float,
    benchmark_type: str,
    benchmark_confidence: Confidence,
    value_per_store_history: list[float],
    outlier_flags: list[str],
    rate_is_imputed: bool,
    config: DistributionConfig,
) -> Confidence:
    cv = coefficient_of_variation(value_per_store_history)
    unstable_rate = cv is not None and cv > config.value_per_store_cv_threshold
    vps_outlier = False
    if len(value_per_store_history) >= 3:
        mask = mad_outlier_mask(pd.Series(value_per_store_history), config.mad_threshold)
        vps_outlier = bool(mask.iloc[-1]) if len(mask) else False

    flags = list(outlier_flags)
    if current_stores <= 0 or rate_is_imputed or n_periods < config.min_history_for_medium_confidence:
        return "LOW"
    if flags or vps_outlier or unstable_rate or benchmark_type == "historical_peak":
        if n_periods >= config.min_history_for_medium_confidence:
            return "MEDIUM" if benchmark_confidence != "LOW" else "LOW"
        return "LOW"
    if (
        n_periods >= config.min_history_for_high_confidence
        and benchmark_confidence == "HIGH"
        and benchmark_type in {"recent_high", "historical_average", "retailer_peer"}
        and current_stores > 0
        and not rate_is_imputed
    ):
        return "HIGH"
    if n_periods >= config.min_history_for_medium_confidence or benchmark_type == "retailer_peer":
        return "MEDIUM"
    return "LOW"
