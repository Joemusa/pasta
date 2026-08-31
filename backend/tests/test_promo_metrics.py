"""Volume/store, value/store, uplift, and opportunity arithmetic."""

from __future__ import annotations

import pytest

from backend.agents.promotion.metrics import (
    incremental_value,
    incremental_volume,
    material_distribution_change,
    price_discount_pct,
    summarise_rates,
    uplift_pct,
    value_per_store,
    volume_per_store,
)


def test_volume_per_store() -> None:
    assert volume_per_store(20.0, 4.0) == 5.0
    assert volume_per_store(100.0, 0.0) is None
    assert volume_per_store(10.0, None) is None
    assert volume_per_store(None, 10.0) is None


def test_value_per_store() -> None:
    assert value_per_store(100.0, 10.0) == 10.0
    assert value_per_store(50.0, 0.0) is None
    assert value_per_store(None, 5.0) is None


def test_uplift_pct() -> None:
    assert uplift_pct(12.0, 10.0) == pytest.approx(0.2)
    assert uplift_pct(8.0, 10.0) == pytest.approx(-0.2)
    assert uplift_pct(10.0, 0.0) is None
    assert uplift_pct(None, 10.0) is None
    assert uplift_pct(10.0, None) is None


def test_price_discount_pct() -> None:
    assert price_discount_pct(8.0, 10.0) == pytest.approx(0.2)
    assert price_discount_pct(None, 10.0) is None
    assert price_discount_pct(8.0, 0.0) is None


def test_summarise_rates_median_and_mean() -> None:
    assert summarise_rates([1.0, 2.0, 3.0], "median") == 2.0
    assert summarise_rates([1.0, 2.0, 3.0], "mean") == 2.0
    assert summarise_rates([], "median") is None


def test_incremental_volume_is_conservative() -> None:
    result = incremental_volume(
        baseline_volume_per_store=10.0,
        volume_uplift=0.4,
        store_count=10.0,
        capture_rate=0.25,
    )
    assert result == pytest.approx(10.0)
    assert (
        incremental_volume(
            baseline_volume_per_store=10.0,
            volume_uplift=-0.1,
            store_count=10.0,
            capture_rate=0.25,
        )
        == 0.0
    )
    assert (
        incremental_volume(
            baseline_volume_per_store=10.0,
            volume_uplift=0.4,
            store_count=0.0,
            capture_rate=0.25,
        )
        is None
    )


def test_incremental_value_does_not_fill_missing_price() -> None:
    assert incremental_value(10.0, 12.5) == 125.0
    assert incremental_value(10.0, None) is None
    assert incremental_value(None, 12.5) is None
    assert incremental_value(10.0, 0.0) is None


def test_material_distribution_change() -> None:
    assert material_distribution_change(10.0, 10.0, 0.5) is False
    assert material_distribution_change(20.0, 8.0, 0.5) is True
    assert material_distribution_change(None, 10.0, 0.5) is False
