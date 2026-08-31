"""Flag price and rate outliers without deleting them."""

from __future__ import annotations

import pandas as pd


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
