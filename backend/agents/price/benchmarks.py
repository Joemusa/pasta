"""Price benchmarks. Insufficient samples produce no benchmark. RSP is never used."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.agents.price.metrics import value_per_store, volume_per_store
from backend.agents.price.models import BenchmarkType, PriceConfig, PromotionStatus
from backend.agents.price.promotion import promotion_is_controlled


@dataclass(frozen=True)
class BenchmarkResult:
    price: float | None
    volume_per_store: float | None
    value_per_store: float | None
    n: int
    benchmark_type: BenchmarkType
    mixed_promotion: bool
    like_for_like: bool


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(pd.Series(values, dtype="float64").median())


def _peer_rows(
    current: pd.DataFrame,
    *,
    product: str,
    retailer: str,
    region: str,
    brand: str | None,
    kind: BenchmarkType,
) -> pd.DataFrame:
    if kind == BenchmarkType.RETAILER_PEER:
        return current.loc[
            (current["product"] == product) & (current["region"] == region) & (current["retailer"] != retailer)
        ]
    if kind == BenchmarkType.REGIONAL_PEER:
        return current.loc[
            (current["product"] == product) & (current["retailer"] == retailer) & (current["region"] != region)
        ]
    if kind == BenchmarkType.CATEGORY_PEER:
        if brand is None or brand == "" or pd.isna(brand):
            return current.iloc[0:0]
        return current.loc[
            (current["retailer"] == retailer)
            & (current["region"] == region)
            & (current["brand"] == brand)
            & (current["product"] != product)
        ]
    if kind == BenchmarkType.SKU_NETWORK:
        return current.loc[
            (current["product"] == product) & ~((current["retailer"] == retailer) & (current["region"] == region))
        ]
    return current.iloc[0:0]


def _summarise(
    frame: pd.DataFrame,
    *,
    status: PromotionStatus,
    kind: BenchmarkType,
    min_n: int,
) -> BenchmarkResult | None:
    if frame.empty:
        return None
    like = frame.loc[frame["promotion_status"] == status.value] if promotion_is_controlled(status) else frame.iloc[0:0]
    mixed = False
    used = like
    if len(used) < min_n:
        used = frame
        mixed = promotion_is_controlled(status) and bool((frame["promotion_status"] != status.value).any())
        if not promotion_is_controlled(status):
            mixed = True
    prices = [float(v) for v in used["realised_price"].dropna().tolist()]
    if len(prices) < min_n:
        return None
    volumes: list[float] = []
    values: list[float] = []
    for row in used.itertuples(index=False):
        vol = volume_per_store(
            float(row.sales_volume) if pd.notna(row.sales_volume) else None,
            float(row.store_count) if pd.notna(row.store_count) else None,
        )
        val = value_per_store(
            float(row.sales_value) if pd.notna(row.sales_value) else None,
            float(row.store_count) if pd.notna(row.store_count) else None,
        )
        if vol is not None:
            volumes.append(vol)
        if val is not None:
            values.append(val)
    like_for_like = (not mixed) and promotion_is_controlled(status) and len(like) >= min_n
    return BenchmarkResult(
        price=_median(prices),
        volume_per_store=_median(volumes),
        value_per_store=_median(values),
        n=len(prices),
        benchmark_type=kind,
        mixed_promotion=mixed,
        like_for_like=like_for_like,
    )


def historical_benchmark(
    history: pd.DataFrame,
    *,
    current_date: pd.Timestamp,
    status: PromotionStatus,
    config: PriceConfig,
) -> BenchmarkResult | None:
    prior = history.loc[history["date"] < current_date]
    if prior.empty:
        return None
    return _summarise(prior, status=status, kind=BenchmarkType.HISTORICAL, min_n=config.min_historical_observations)


def choose_benchmark(
    *,
    current: pd.DataFrame,
    history: pd.DataFrame,
    product: str,
    retailer: str,
    region: str,
    brand: str | None,
    status: PromotionStatus,
    current_date: pd.Timestamp,
    config: PriceConfig,
) -> BenchmarkResult:
    """Prefer like-for-like peers. Historical is last because weeks may overlap as rolling 4-week CY."""
    empty = BenchmarkResult(None, None, None, 0, BenchmarkType.NONE, False, False)
    order = (
        BenchmarkType.RETAILER_PEER,
        BenchmarkType.REGIONAL_PEER,
        BenchmarkType.CATEGORY_PEER,
        BenchmarkType.SKU_NETWORK,
    )
    like_for_like: list[BenchmarkResult] = []
    mixed: list[BenchmarkResult] = []
    for kind in order:
        peers = _peer_rows(current, product=product, retailer=retailer, region=region, brand=brand, kind=kind)
        result = _summarise(peers, status=status, kind=kind, min_n=config.min_peer_observations)
        if result is None:
            continue
        if result.like_for_like:
            like_for_like.append(result)
        else:
            mixed.append(result)
    if like_for_like:
        return like_for_like[0]
    historical = historical_benchmark(history, current_date=current_date, status=status, config=config)
    if historical is not None and historical.like_for_like:
        return historical
    if mixed:
        return mixed[0]
    if historical is not None:
        return historical
    return empty
