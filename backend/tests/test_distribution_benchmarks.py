"""Benchmark selection, spike handling, and peer logic."""

from __future__ import annotations

import pandas as pd

from backend.agents.distribution.benchmarks import UnitHistory, consider_benchmarks, peer_store_counts
from backend.agents.distribution.models import DistributionConfig
from backend.agents.distribution.outliers import is_peak_spike


def _config(**overrides: object) -> DistributionConfig:
    payload = DistributionConfig().model_dump()
    payload.update(overrides)
    return DistributionConfig.model_validate(payload)


def test_peak_spike_is_flagged_and_not_used_as_benchmark() -> None:
    config = _config()
    dates = list(pd.to_datetime(["2026-07-26", "2026-08-02", "2026-08-09", "2026-08-16"]))
    history = UnitHistory(
        dates=dates,
        store_counts=[10.0, 10.0, 40.0, 10.0],
        sales_values=[100.0, 100.0, 400.0, 100.0],
        sales_volumes=[10.0, 10.0, 40.0, 10.0],
    )
    assert is_peak_spike(history.store_counts, config) is True
    chosen, snapshots, spike = consider_benchmarks(
        current_stores=10.0,
        history=history,
        current_date=dates[-1],
        retailer_peers=[],
        regional_peers=[],
        config=config,
    )
    assert spike is True
    assert snapshots["historical_peak"].flagged_spike is True
    assert snapshots["historical_peak"].selected is False
    assert chosen is not None
    assert chosen.benchmark_type == "historical_average"
    assert chosen.benchmark_stores == 18.0


def test_recent_high_preferred_when_peak_is_repeatable() -> None:
    config = _config()
    dates = list(pd.to_datetime(["2026-07-26", "2026-08-02", "2026-08-09", "2026-08-16"]))
    history = UnitHistory(
        dates=dates,
        store_counts=[8.0, 12.0, 11.0, 9.0],
        sales_values=[80.0, 120.0, 110.0, 90.0],
        sales_volumes=[8.0, 12.0, 11.0, 9.0],
    )
    chosen, snapshots, spike = consider_benchmarks(
        current_stores=9.0,
        history=history,
        current_date=dates[-1],
        retailer_peers=[],
        regional_peers=[],
        config=config,
    )
    assert spike is False
    assert chosen is not None
    assert chosen.benchmark_type == "recent_high"
    assert chosen.benchmark_stores == 11.0
    assert snapshots["recent_high"].selected is True


def test_retailer_peer_used_when_history_has_no_gap() -> None:
    config = _config()
    current_date = pd.Timestamp("2026-08-16")
    history = UnitHistory(
        dates=[current_date],
        store_counts=[5.0],
        sales_values=[50.0],
        sales_volumes=[5.0],
    )
    chosen, snapshots, _spike = consider_benchmarks(
        current_stores=5.0,
        history=history,
        current_date=current_date,
        retailer_peers=[12.0, 13.0, 14.0, 15.0, 11.0],
        regional_peers=[],
        config=config,
    )
    assert chosen is not None
    assert chosen.benchmark_type == "retailer_peer"
    assert chosen.benchmark_stores == 13.0
    assert snapshots["retailer_peer"].available is True


def test_regional_peer_scale_filter() -> None:
    config = _config(peer_scale_ratio=4.0, min_peer_observations=3)
    current = pd.DataFrame(
        {
            "sku": ["SKU-A"] * 5,
            "retailer": ["R1", "R2", "R3", "R4", "R5"],
            "region": ["Gauteng"] * 5,
            "store_count": [2.0, 3.0, 4.0, 80.0, 90.0],
        }
    )
    peers = peer_store_counts(
        current, "SKU-A", "R1", "Gauteng", kind="region", config=config, current_stores=2.0
    )
    assert 80.0 not in peers
    assert 90.0 not in peers
    assert sorted(peers) == [3.0, 4.0]


def test_no_opportunity_when_already_at_potential() -> None:
    config = _config()
    current_date = pd.Timestamp("2026-08-16")
    history = UnitHistory(
        dates=[current_date],
        store_counts=[20.0],
        sales_values=[200.0],
        sales_volumes=[20.0],
    )
    chosen, _snapshots, _spike = consider_benchmarks(
        current_stores=20.0,
        history=history,
        current_date=current_date,
        retailer_peers=[18.0, 19.0, 17.0],
        regional_peers=[],
        config=config,
    )
    assert chosen is None
