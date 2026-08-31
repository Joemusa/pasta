"""Documented addressable-opportunity formulas. Specialist calculations are not changed.

Distribution Addressable Value = value_per_store * distribution_store_gap
Distribution Addressable Volume = volume_per_store * distribution_store_gap

These are the value and volume associated with closing the identified distribution gap.
They are not guaranteed incremental sales. No capture-rate assumption is applied here;
any capture rate used by a frozen specialist remains that agent's own methodology.
"""

from __future__ import annotations

ADDRESSABLE_METHODOLOGY = (
    "Distribution Addressable Value = value_per_store * distribution_store_gap. "
    "Distribution Addressable Volume = volume_per_store * distribution_store_gap. "
    "These equal the frozen Distribution Agent opportunity (value_per_store x store_gap and "
    "volume_per_store x store_gap). They represent the value/volume associated with closing "
    "the identified distribution gap. They are not guaranteed incremental sales. "
    "Current sales are reported separately and are never treated as the opportunity. "
    "The Commercial Brain does not apply a capture rate; it does not re-score specialist agents. "
    "Overlapping distribution, price, and promotion values are not summed."
)


def distribution_addressable_value(value_per_store: float, store_gap: float) -> float:
    """value_per_store x distribution_store_gap. Not guaranteed incremental sales."""
    return round(value_per_store * store_gap, 2)


def distribution_addressable_volume(volume_per_store: float, store_gap: float) -> float:
    """volume_per_store x distribution_store_gap. Not guaranteed incremental sales."""
    return round(volume_per_store * store_gap, 4)
