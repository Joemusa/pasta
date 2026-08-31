"""Automated tests for Distribution Agent commercial metrics."""

from __future__ import annotations

from backend.agents.distribution.metrics import (
    distribution_gap,
    round_stores,
    value_opportunity,
    value_per_store,
    volume_opportunity,
    volume_per_store,
)


def test_value_per_store() -> None:
    assert value_per_store(100.0, 10.0) == 10.0
    assert value_per_store(50.0, 4.0) == 12.5


def test_volume_per_store() -> None:
    assert volume_per_store(20.0, 4.0) == 5.0


def test_value_and_volume_per_store_zero_and_missing() -> None:
    assert value_per_store(100.0, 0.0) is None
    assert volume_per_store(20.0, 0.0) is None
    assert value_per_store(None, 10.0) is None
    assert volume_per_store(10.0, None) is None
    assert value_per_store(100.0, -1.0) is None


def test_distribution_gap() -> None:
    assert distribution_gap(10.0, 15.0) == 5.0
    assert distribution_gap(15.0, 10.0) == 0.0
    assert distribution_gap(8.0, 8.0) == 0.0
    assert distribution_gap(None, 10.0) is None
    assert distribution_gap(10.0, None) is None


def test_value_and_volume_opportunity() -> None:
    assert value_opportunity(5.0, 12.5) == 62.5
    assert volume_opportunity(5.0, 2.0) == 10.0
    assert value_opportunity(None, 12.5) is None
    assert volume_opportunity(3.0, None) is None


def test_round_stores_half_up() -> None:
    assert round_stores(10.4) == 10.0
    assert round_stores(10.5) == 11.0
    assert round_stores(2.0) == 2.0
