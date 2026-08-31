"""Pure Promotion Agent V1 metrics. Missing inputs stay missing."""

from __future__ import annotations

import math

import pandas as pd


def _finite(value: float | None) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(float(value))


def volume_per_store(sales_volume: float | None, store_count: float | None) -> float | None:
    """Sales volume / store count. None when stores are missing or not positive."""
    if not _finite(sales_volume) or not _finite(store_count):
        return None
    if store_count <= 0:
        return None
    return float(sales_volume) / float(store_count)


def value_per_store(sales_value: float | None, store_count: float | None) -> float | None:
    """Sales value / store count. None when stores are missing or not positive."""
    if not _finite(sales_value) or not _finite(store_count):
        return None
    if store_count <= 0:
        return None
    return float(sales_value) / float(store_count)


def uplift_pct(promo_rate: float | None, baseline_rate: float | None) -> float | None:
    """(promo - baseline) / baseline. None when baseline is missing or not positive."""
    if not _finite(promo_rate) or not _finite(baseline_rate):
        return None
    if baseline_rate <= 0:
        return None
    return (float(promo_rate) - float(baseline_rate)) / float(baseline_rate)


def price_discount_pct(promo_price: float | None, regular_price: float | None) -> float | None:
    """(regular - promo) / regular. None when either side is missing or regular is not positive."""
    if not _finite(promo_price) or not _finite(regular_price):
        return None
    if regular_price <= 0:
        return None
    return (float(regular_price) - float(promo_price)) / float(regular_price)


def summarise_rates(values: list[float], statistic: str = "median") -> float | None:
    if not values:
        return None
    series = pd.Series(values, dtype="float64")
    if statistic == "mean":
        return float(series.mean())
    return float(series.median())


def incremental_volume(
    *,
    baseline_volume_per_store: float | None,
    volume_uplift: float | None,
    store_count: float | None,
    capture_rate: float,
) -> float | None:
    """Baseline volume × estimated uplift × capture rate. Not causal incrementality."""
    if not _finite(baseline_volume_per_store) or not _finite(volume_uplift) or not _finite(store_count):
        return None
    if store_count <= 0 or capture_rate < 0:
        return None
    if volume_uplift <= 0:
        return 0.0
    baseline_volume = float(baseline_volume_per_store) * float(store_count)
    return baseline_volume * float(volume_uplift) * float(capture_rate)


def incremental_value(extra_volume: float | None, unit_price: float | None) -> float | None:
    """Incremental volume times realised/promotional price. Does not fill missing price with zero."""
    if not _finite(extra_volume) or not _finite(unit_price):
        return None
    if unit_price <= 0:
        return None
    return float(extra_volume) * float(unit_price)


def material_distribution_change(
    promo_stores: float | None,
    baseline_stores: float | None,
    change_ratio: float,
) -> bool:
    """True when median store counts of the two groups differ by more than change_ratio."""
    if not _finite(promo_stores) or not _finite(baseline_stores):
        return False
    base = max(float(promo_stores), float(baseline_stores), 1e-9)
    return abs(float(promo_stores) - float(baseline_stores)) / base > change_ratio
