"""Pure commercial metrics for the Distribution Agent."""

from __future__ import annotations

import math


def _finite(value: float | None) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(float(value))


def value_per_store(sales_value: float | None, store_count: float | None) -> float | None:
    """Sales value / store count. Returns None for missing or non-positive stores."""
    if not _finite(sales_value) or not _finite(store_count):
        return None
    if store_count <= 0:
        return None
    return float(sales_value) / float(store_count)


def volume_per_store(sales_volume: float | None, store_count: float | None) -> float | None:
    """Sales volume / store count. Returns None for missing or non-positive stores."""
    if not _finite(sales_volume) or not _finite(store_count):
        return None
    if store_count <= 0:
        return None
    return float(sales_volume) / float(store_count)


def distribution_gap(current_stores: float | None, potential_stores: float | None) -> float | None:
    """Potential stores minus current stores, floored at zero. None if either side is missing."""
    if not _finite(current_stores) or not _finite(potential_stores):
        return None
    return max(0.0, float(potential_stores) - float(current_stores))


def value_opportunity(store_gap: float | None, value_per_store_rate: float | None) -> float | None:
    """Distribution gap times value per store. None if either input is missing."""
    if not _finite(store_gap) or not _finite(value_per_store_rate):
        return None
    return float(store_gap) * float(value_per_store_rate)


def volume_opportunity(store_gap: float | None, volume_per_store_rate: float | None) -> float | None:
    """Distribution gap times volume per store. None if either input is missing."""
    if not _finite(store_gap) or not _finite(volume_per_store_rate):
        return None
    return float(store_gap) * float(volume_per_store_rate)


def round_stores(value: float) -> float:
    """Commercial half-up rounding to a whole store."""
    if value >= 0:
        return float(math.floor(value + 0.5))
    return float(math.ceil(value - 0.5))
