"""Pure Price Agent V1 metrics. Missing inputs stay missing."""

from __future__ import annotations

import math


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


def price_index(sku_price: float | None, benchmark_price: float | None) -> float | None:
    """SKU price / benchmark price. None when either side is missing or benchmark is not positive."""
    if not _finite(sku_price) or not _finite(benchmark_price):
        return None
    if benchmark_price <= 0:
        return None
    return float(sku_price) / float(benchmark_price)


def price_difference_pct(sku_price: float | None, benchmark_price: float | None) -> float | None:
    """(SKU - benchmark) / benchmark * 100. None when the index cannot be formed."""
    index = price_index(sku_price, benchmark_price)
    if index is None:
        return None
    return (index - 1.0) * 100.0


def volume_gap_opportunity(
    *,
    current_volume_per_store: float | None,
    peer_volume_per_store: float | None,
    store_count: float | None,
    capture_rate: float,
) -> float | None:
    """Conservative extra volume from a like-for-like volume/store gap. Not an elasticity."""
    if not _finite(current_volume_per_store) or not _finite(peer_volume_per_store) or not _finite(store_count):
        return None
    if store_count <= 0 or capture_rate < 0:
        return None
    gap = max(0.0, float(peer_volume_per_store) - float(current_volume_per_store))
    return gap * float(store_count) * float(capture_rate)


def value_from_extra_volume(extra_volume: float | None, unit_price: float | None) -> float | None:
    """Extra volume times a price. None if either input is missing. Does not fill missing price with zero."""
    if not _finite(extra_volume) or not _finite(unit_price):
        return None
    if unit_price <= 0:
        return None
    return float(extra_volume) * float(unit_price)


def value_from_price_gap(
    *,
    current_volume: float | None,
    current_price: float | None,
    benchmark_price: float | None,
    capture_rate: float,
) -> float | None:
    """Conservative value from a price-to-benchmark gap at current volume. Volume is not assumed to hold."""
    if not _finite(current_volume) or not _finite(current_price) or not _finite(benchmark_price):
        return None
    if current_volume < 0 or capture_rate < 0:
        return None
    gap = float(benchmark_price) - float(current_price)
    if gap <= 0:
        return 0.0
    return float(current_volume) * gap * float(capture_rate)
