"""Price benchmarks require sample size and never use RSP as normal price."""

from __future__ import annotations

import pandas as pd

from backend.agents.price.benchmarks import choose_benchmark
from backend.agents.price.evaluate import attach_derived
from backend.agents.price.models import BenchmarkType, PriceConfig, PromotionStatus
from backend.tests.price_helpers import panel_for_product


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = attach_derived(pd.DataFrame(rows), PriceConfig())
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def test_regional_peer_median_price() -> None:
    rows = panel_for_product(target_price=20.0, peer_price=10.0)
    frame = _frame(rows)
    current = frame.loc[frame["date"] == frame["date"].max()]
    history = frame.loc[
        (frame["product"] == "Handy Andy Lemon 750ml")
        & (frame["retailer"] == "Checkers")
        & (frame["region"] == "Gauteng")
    ]
    result = choose_benchmark(
        current=current,
        history=history,
        product="Handy Andy Lemon 750ml",
        retailer="Checkers",
        region="Gauteng",
        brand="Handy Andy",
        status=PromotionStatus.NON_PROMOTION,
        current_date=current["date"].max(),
        config=PriceConfig(),
    )
    assert result.benchmark_type == BenchmarkType.REGIONAL_PEER
    assert result.price == 10.0
    assert result.like_for_like is True
    assert result.n == 3


def test_insufficient_peers_yield_no_benchmark() -> None:
    rows = panel_for_product(target_price=20.0, peer_price=10.0)
    frame = _frame(rows)
    current = frame.loc[
        (frame["date"] == frame["date"].max())
        & (frame["region"].isin(["Gauteng", "Western Cape"]))
    ]
    history = current.iloc[0:0]
    result = choose_benchmark(
        current=current,
        history=history,
        product="Handy Andy Lemon 750ml",
        retailer="Checkers",
        region="Gauteng",
        brand="Handy Andy",
        status=PromotionStatus.NON_PROMOTION,
        current_date=current["date"].max(),
        config=PriceConfig(min_peer_observations=3, min_historical_observations=2),
    )
    assert result.benchmark_type == BenchmarkType.NONE
    assert result.price is None


def test_rsp_column_is_not_used_as_benchmark() -> None:
    rows = panel_for_product(target_price=20.0, peer_price=10.0)
    for row in rows:
        row["off_promo_rsp"] = 99.0
        row["on_promo_rsp"] = 99.0
    frame = _frame(rows)
    current = frame.loc[frame["date"] == frame["date"].max()]
    history = frame
    result = choose_benchmark(
        current=current,
        history=history,
        product="Handy Andy Lemon 750ml",
        retailer="Checkers",
        region="Gauteng",
        brand="Handy Andy",
        status=PromotionStatus.NON_PROMOTION,
        current_date=current["date"].max(),
        config=PriceConfig(),
    )
    assert result.price == 10.0
    assert result.price != 99.0
