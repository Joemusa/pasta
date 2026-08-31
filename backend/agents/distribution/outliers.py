"""Flag distribution outliers without deleting them."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from backend.agents.distribution.models import DistributionConfig


def mad_outlier_mask(values: pd.Series, threshold: float) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return pd.Series(False, index=values.index)
    median = float(numeric.median())
    abs_dev = (numeric - median).abs()
    mad = float(abs_dev.median())
    if mad == 0:
        std = float(numeric.std(ddof=0))
        if std == 0:
            flags = pd.Series(False, index=numeric.index)
        else:
            flags = ((numeric - median) / std).abs() > threshold
    else:
        flags = (0.6745 * (numeric - median) / mad).abs() > threshold
    return flags.reindex(values.index, fill_value=False)


def is_peak_spike(store_counts: Sequence[float], config: DistributionConfig) -> bool:
    """True when the historical peak looks like a one-off spike rather than achievable potential."""
    series = [float(v) for v in store_counts if v is not None and pd.notna(v)]
    if len(series) < config.min_periods_to_flag_spike:
        return False
    peak = max(series)
    peak_hits = sum(1 for value in series if value == peak)
    if peak_hits != 1:
        return False
    others = [value for value in series if value != peak]
    if not others:
        return False
    median_others = float(pd.Series(others).median())
    if median_others <= 0:
        return peak >= median_others + max(1.0, config.spike_ratio)
    if peak >= median_others * config.spike_ratio:
        return True
    flagged = mad_outlier_mask(pd.Series(series), config.mad_threshold)
    peak_index = series.index(peak)
    return bool(flagged.iloc[peak_index])
