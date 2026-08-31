"""Volume/store, value/store, price index, and opportunity arithmetic."""

from __future__ import annotations

import pytest

from backend.agents.price.metrics import (
    price_difference_pct,
    price_index,
    value_from_extra_volume,
    value_from_price_gap,
    value_per_store,
    volume_gap_opportunity,
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


def test_price_index_and_difference() -> None:
    assert price_index(12.0, 10.0) == pytest.approx(1.2)
    assert price_difference_pct(12.0, 10.0) == pytest.approx(20.0)
    assert price_index(10.0, 0.0) is None
    assert price_index(None, 10.0) is None
    assert price_index(10.0, None) is None
    assert price_difference_pct(10.0, None) is None


def test_volume_gap_opportunity_is_conservative() -> None:
    result = volume_gap_opportunity(
        current_volume_per_store=8.0,
        peer_volume_per_store=12.0,
        store_count=10.0,
        capture_rate=0.25,
    )
    assert result == 10.0
    assert volume_gap_opportunity(
        current_volume_per_store=12.0,
        peer_volume_per_store=8.0,
        store_count=10.0,
        capture_rate=0.25,
    ) == 0.0
    assert volume_gap_opportunity(
        current_volume_per_store=8.0,
        peer_volume_per_store=12.0,
        store_count=0.0,
        capture_rate=0.25,
    ) is None


def test_value_from_extra_volume_does_not_fill_missing_price() -> None:
    assert value_from_extra_volume(10.0, 12.5) == 125.0
    assert value_from_extra_volume(10.0, None) is None
    assert value_from_extra_volume(None, 12.5) is None
    assert value_from_extra_volume(10.0, 0.0) is None


def test_value_from_price_gap() -> None:
    assert value_from_price_gap(
        current_volume=100.0,
        current_price=8.0,
        benchmark_price=10.0,
        capture_rate=0.25,
    ) == 50.0
    assert value_from_price_gap(
        current_volume=100.0,
        current_price=10.0,
        benchmark_price=8.0,
        capture_rate=0.25,
    ) == 0.0
    assert value_from_price_gap(
        current_volume=100.0,
        current_price=None,
        benchmark_price=10.0,
        capture_rate=0.25,
    ) is None
