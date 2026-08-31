"""Directional price signals, recommendations, and estimated opportunities.

Not a causal elasticity model. Promotion-mixed comparisons are flagged.
Distribution-primary cases are not recommended as price tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.agents.price.benchmarks import BenchmarkResult, choose_benchmark
from backend.agents.price.metrics import (
    price_difference_pct,
    price_index,
    value_from_extra_volume,
    value_from_price_gap,
    value_per_store,
    volume_gap_opportunity,
    volume_per_store,
)
from backend.agents.price.models import (
    BenchmarkType,
    PriceConfig,
    PriceOpportunity,
    PriceSignal,
    PromotionStatus,
    Recommendation,
)
from backend.agents.price.outliers import mad_outlier_mask
from backend.agents.price.promotion import classify_promotion, promotion_is_controlled

LOWER_METHODOLOGY = (
    "Estimated price opportunity: like-for-like volume/store gap vs the selected benchmark "
    "group, times current store count, times conservative capture rate. Value uses extra "
    "volume times current realised price. This is directional, not an elasticity, and not "
    "guaranteed incremental sales."
)
INCREASE_METHODOLOGY = (
    "Estimated price opportunity: current volume times the price-to-benchmark gap times "
    "conservative capture rate. Volume is not assumed to hold at a higher price. This is "
    "directional, not an elasticity, and not guaranteed incremental sales."
)
ARCHITECTURE_METHODOLOGY = (
    "Price architecture review: the SKU's realised prices differ materially across "
    "retailers/regions in the current period. No incremental volume is assumed."
)
MAINTAIN_METHODOLOGY = (
    "No quantified price test: current realised price is aligned with the available "
    "like-for-like benchmark, or evidence is not strong enough for a change test."
)
INSUFFICIENT_METHODOLOGY = (
    "No estimated price opportunity: sample size, promotion control, distribution, or "
    "price coverage is insufficient for a directional test."
)


@dataclass
class Evaluation:
    recommendation: Recommendation
    signal: PriceSignal
    opportunity: PriceOpportunity | None = None
    limitations: list[str] = field(default_factory=list)


def _finite_price(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if number <= 0:
        return None
    return number


def attach_derived(frame: pd.DataFrame, config: PriceConfig) -> pd.DataFrame:
    out = frame.copy()
    statuses: list[str] = []
    sources: list[str] = []
    for row in out.to_dict(orient="records"):
        status, source = classify_promotion(row, config)
        statuses.append(status.value)
        sources.append(source)
    out["promotion_status"] = statuses
    out["promo_source"] = sources
    out["realised_price"] = pd.to_numeric(out["pos_current_price"], errors="coerce")
    return out


def _distribution_primary(
    *,
    stores: float | None,
    volume: float | None,
    peer_stores: float | None,
    peer_volume_per_store: float | None,
    current_volume_per_store: float | None,
    config: PriceConfig,
) -> bool:
    if stores is None:
        return False
    low_dist = False
    if peer_stores is not None and peer_stores > 0:
        low_dist = stores < peer_stores * config.low_distribution_ratio
        low_dist = low_dist and (peer_stores - stores) >= config.min_store_gap
    if stores <= 0:
        low_dist = True
    low_sales = False
    if current_volume_per_store is not None and peer_volume_per_store is not None and peer_volume_per_store > 0:
        low_sales = current_volume_per_store < peer_volume_per_store * config.low_sales_ratio
    elif volume is not None and volume <= 0:
        low_sales = True
    return bool(low_dist and low_sales)


def _peer_store_median(current: pd.DataFrame, product: str, retailer: str, region: str) -> float | None:
    peers = current.loc[
        (current["product"] == product) & (current["retailer"] == retailer) & (current["region"] != region)
    ]
    if len(peers) < 3:
        peers = current.loc[
            (current["product"] == product) & (current["region"] == region) & (current["retailer"] != retailer)
        ]
    stores = pd.to_numeric(peers["store_count"], errors="coerce").dropna()
    if len(stores) < 3:
        return None
    return float(stores.median())


def _architecture_spread(current: pd.DataFrame, product: str, config: PriceConfig) -> tuple[bool, float | None]:
    prices = pd.to_numeric(
        current.loc[current["product"] == product, "realised_price"],
        errors="coerce",
    ).dropna()
    prices = prices[prices > 0]
    if len(prices) < config.min_architecture_locations:
        return False, None
    minimum = float(prices.min())
    maximum = float(prices.max())
    if minimum <= 0:
        return False, None
    spread = maximum / minimum
    return spread >= config.architecture_spread_ratio, float(prices.median())


def _outliers(history: pd.DataFrame, current_price: float | None, config: PriceConfig) -> list[str]:
    flags: list[str] = []
    prices = pd.to_numeric(history["realised_price"], errors="coerce")
    if current_price is not None and prices.notna().sum() >= 3:
        mask = mad_outlier_mask(prices, config.mad_threshold)
        last = history["date"].idxmax() if len(history) else None
        if last is not None and bool(mask.get(last, False)):
            flags.append("price_outlier")
    rates: list[float] = []
    index: list[object] = []
    for row in history.itertuples(index=True):
        rate = volume_per_store(
            float(row.sales_volume) if pd.notna(row.sales_volume) else None,
            float(row.store_count) if pd.notna(row.store_count) else None,
        )
        if rate is not None:
            rates.append(rate)
            index.append(row.Index)
    if len(rates) >= 3:
        series = pd.Series(rates, index=index)
        mask = mad_outlier_mask(series, config.mad_threshold)
        last = history["date"].idxmax()
        if last in mask.index and bool(mask.loc[last]):
            flags.append("volume_per_store_outlier")
    return flags


def _signal(
    *,
    index: float | None,
    vol: float | None,
    peer_vol: float | None,
    value_rate: float | None,
    peer_value: float | None,
    config: PriceConfig,
) -> PriceSignal:
    if index is None:
        return PriceSignal.UNCLEAR
    high = index >= 1.0 + config.price_gap_pct
    low = index <= 1.0 - config.price_gap_pct
    vol_low = (
        vol is not None and peer_vol is not None and peer_vol > 0 and vol < peer_vol * (1.0 - config.volume_gap_pct)
    )
    vol_high = (
        vol is not None and peer_vol is not None and peer_vol > 0 and vol > peer_vol * (1.0 + config.volume_gap_pct)
    )
    vol_stable = (
        vol is not None
        and peer_vol is not None
        and peer_vol > 0
        and (not vol_low)
        and (not vol_high)
    )
    value_low = (
        value_rate is not None
        and peer_value is not None
        and peer_value > 0
        and value_rate < peer_value * (1.0 - config.value_gap_pct)
    )
    if high and vol_low:
        return PriceSignal.HIGHER_PRICE_LOWER_VOLUME
    if low and vol_high:
        return PriceSignal.LOWER_PRICE_HIGHER_VOLUME
    if high and vol_stable:
        return PriceSignal.HIGHER_PRICE_STABLE_VOLUME
    if low and value_low:
        return PriceSignal.LOWER_PRICE_LOWER_VALUE
    if not high and not low:
        return PriceSignal.ALIGNED
    return PriceSignal.UNCLEAR


def _confidence(
    *,
    n_weeks: int,
    benchmark: BenchmarkResult,
    promo_source: str,
    mixed: bool,
    distribution_primary: bool,
    outliers: list[str],
    recommendation: Recommendation,
    config: PriceConfig,
) -> str:
    if recommendation == Recommendation.INSUFFICIENT_EVIDENCE:
        return "LOW"
    if n_weeks >= config.min_history_for_high_confidence and not mixed and not outliers and not distribution_primary:
        if benchmark.like_for_like and promo_source == "pos":
            return "HIGH"
    medium_ok = (
        n_weeks >= config.min_history_for_medium_confidence
        and benchmark.like_for_like
        and promo_source == "pos"
        and not mixed
        and not distribution_primary
        and not outliers
        and recommendation != Recommendation.INSUFFICIENT_EVIDENCE
    )
    if medium_ok and recommendation in {
        Recommendation.LOWER_PRICE_TEST,
        Recommendation.PRICE_INCREASE_TEST,
        Recommendation.MAINTAIN_PRICE,
    }:
        return "MEDIUM"
    if recommendation == Recommendation.PRICE_ARCHITECTURE_REVIEW and n_weeks >= 1:
        return "LOW"
    return "LOW"


def evaluate_grain(
    *,
    row: pd.Series,
    current: pd.DataFrame,
    history: pd.DataFrame,
    current_date: pd.Timestamp,
    config: PriceConfig,
) -> Evaluation:
    product = str(row["product"])
    retailer = str(row["retailer"])
    region = str(row["region"])
    brand = None if pd.isna(row.get("brand")) else str(row["brand"])
    price = _finite_price(row.get("realised_price"))
    stores = float(row["store_count"]) if pd.notna(row.get("store_count")) else None
    sales_value = float(row["sales_value"]) if pd.notna(row.get("sales_value")) else None
    sales_volume = float(row["sales_volume"]) if pd.notna(row.get("sales_volume")) else None
    status = PromotionStatus(str(row["promotion_status"]))
    promo_source = str(row.get("promo_source") or "missing")
    n_weeks = int(history["date"].nunique()) if len(history) else 1
    vol = volume_per_store(sales_volume, stores)
    val = value_per_store(sales_value, stores)
    limitations: list[str] = [
        "Price history is short and overlapping weeks may share rolling 4 Weeks CY measures.",
        "off_promo_rsp / on_promo_rsp is not used as normal price.",
        "Findings are directional and are not causal elasticity.",
    ]
    ambiguous = row.get("flag_ambiguous_product_mapping")
    if pd.notna(ambiguous) and bool(ambiguous):
        limitations.append("Product name maps to multiple ProductsID values at this grain.")
    if promo_source == "rolling_4w_cy":
        limitations.append("Promotion status uses rolling 4 Weeks CY extract fields, not a clean weekly flag.")
    if promo_source == "missing":
        limitations.append("Promotion metrics are missing; promotion cannot be controlled.")

    if price is None:
        return Evaluation(
            Recommendation.INSUFFICIENT_EVIDENCE,
            PriceSignal.UNCLEAR,
            limitations=[*limitations, "Current realised price is missing."],
        )

    benchmark = choose_benchmark(
        current=current,
        history=history,
        product=product,
        retailer=retailer,
        region=region,
        brand=brand,
        status=status,
        current_date=current_date,
        config=config,
    )
    index = price_index(price, benchmark.price)
    diff_pct = price_difference_pct(price, benchmark.price)
    signal = _signal(
        index=index,
        vol=vol,
        peer_vol=benchmark.volume_per_store,
        value_rate=val,
        peer_value=benchmark.value_per_store,
        config=config,
    )
    peer_stores = _peer_store_median(current, product, retailer, region)
    dist_primary = _distribution_primary(
        stores=stores,
        volume=sales_volume,
        peer_stores=peer_stores,
        peer_volume_per_store=benchmark.volume_per_store,
        current_volume_per_store=vol,
        config=config,
    )
    if dist_primary:
        limitations.append("Distribution likely primary lever")
    outliers = _outliers(history, price, config)
    architecture, sku_median = _architecture_spread(current, product, config)
    mixed = benchmark.mixed_promotion
    if mixed:
        limitations.append("Benchmark mixes promotion states or promotion is uncontrolled.")
    if benchmark.benchmark_type == BenchmarkType.HISTORICAL:
        limitations.append("Benchmark is own-grain history; overlapping rolling windows reduce independence.")
    if benchmark.benchmark_type == BenchmarkType.NONE:
        limitations.append("No price benchmark met the minimum sample size.")

    sample_size = n_weeks + benchmark.n
    recommendation = Recommendation.INSUFFICIENT_EVIDENCE
    methodology = INSUFFICIENT_METHODOLOGY
    est_vol = 0.0
    est_val = 0.0

    same_sku_benchmark = benchmark.benchmark_type in {
        BenchmarkType.RETAILER_PEER,
        BenchmarkType.REGIONAL_PEER,
        BenchmarkType.SKU_NETWORK,
        BenchmarkType.HISTORICAL,
    }
    can_test = (
        n_weeks >= config.min_weeks_for_recommendation
        and promotion_is_controlled(status)
        and promo_source == "pos"
        and benchmark.like_for_like
        and not mixed
        and benchmark.price is not None
        and index is not None
        and same_sku_benchmark
    )

    if can_test and dist_primary and signal == PriceSignal.HIGHER_PRICE_LOWER_VOLUME:
        recommendation = Recommendation.INSUFFICIENT_EVIDENCE
        methodology = INSUFFICIENT_METHODOLOGY
    elif can_test and signal == PriceSignal.HIGHER_PRICE_LOWER_VOLUME and not dist_primary:
        extra = volume_gap_opportunity(
            current_volume_per_store=vol,
            peer_volume_per_store=benchmark.volume_per_store,
            store_count=stores,
            capture_rate=config.capture_rate,
        )
        value = value_from_extra_volume(extra, price)
        if extra is not None and value is not None and value >= config.min_value_opportunity:
            recommendation = Recommendation.LOWER_PRICE_TEST
            methodology = LOWER_METHODOLOGY + f" Capture rate={config.capture_rate}."
            est_vol = round(extra, 4)
            est_val = round(value, 2)
    elif can_test and signal == PriceSignal.LOWER_PRICE_LOWER_VALUE and not dist_primary:
        value = value_from_price_gap(
            current_volume=sales_volume,
            current_price=price,
            benchmark_price=benchmark.price,
            capture_rate=config.capture_rate,
        )
        if value is not None and value >= config.min_value_opportunity:
            recommendation = Recommendation.PRICE_INCREASE_TEST
            methodology = INCREASE_METHODOLOGY + f" Capture rate={config.capture_rate}."
            est_vol = 0.0
            est_val = round(value, 2)
    elif can_test and signal in {PriceSignal.ALIGNED, PriceSignal.HIGHER_PRICE_STABLE_VOLUME}:
        recommendation = Recommendation.MAINTAIN_PRICE
        methodology = MAINTAIN_METHODOLOGY
    elif can_test and signal == PriceSignal.LOWER_PRICE_HIGHER_VOLUME:
        recommendation = Recommendation.MAINTAIN_PRICE
        methodology = MAINTAIN_METHODOLOGY
        limitations.append("Lower price with higher volume/store is directional only and is not a change test.")
    elif (
        n_weeks >= config.min_weeks_for_recommendation
        and signal == PriceSignal.ALIGNED
        and benchmark.price is not None
    ):
        recommendation = Recommendation.MAINTAIN_PRICE
        methodology = MAINTAIN_METHODOLOGY

    if recommendation == Recommendation.INSUFFICIENT_EVIDENCE and architecture and sku_median is not None:
        extreme = bool(sku_median) and abs((price / sku_median) - 1.0) >= config.price_gap_pct
        if extreme:
            recommendation = Recommendation.PRICE_ARCHITECTURE_REVIEW
            methodology = ARCHITECTURE_METHODOLOGY

    confidence = _confidence(
        n_weeks=n_weeks,
        benchmark=benchmark,
        promo_source=promo_source,
        mixed=mixed,
        distribution_primary=dist_primary,
        outliers=outliers,
        recommendation=recommendation,
        config=config,
    )
    emit = recommendation in {
        Recommendation.LOWER_PRICE_TEST,
        Recommendation.PRICE_INCREASE_TEST,
        Recommendation.PRICE_ARCHITECTURE_REVIEW,
    }
    opportunity = None
    if emit:
        period = current_date.strftime("%Y-%m-%d")
        opportunity = PriceOpportunity(
            opportunity_id=f"{period}|{product}|{retailer}|{region}",
            product=product,
            brand=brand,
            retailer=retailer,
            region=region,
            current_price=round(price, 4),
            benchmark_price=None if benchmark.price is None else round(benchmark.price, 4),
            price_difference_pct=None if diff_pct is None else round(diff_pct, 4),
            price_index=None if index is None else round(index, 4),
            volume_per_store=None if vol is None else round(vol, 4),
            value_per_store=None if val is None else round(val, 4),
            store_count=None if stores is None else round(stores, 4),
            promotion_status=status.value,
            price_signal=signal.value,
            recommendation=recommendation.value,
            estimated_volume_opportunity=est_vol,
            estimated_value_opportunity=est_val,
            confidence=confidence,  # type: ignore[arg-type]
            sample_size=sample_size,
            n_weeks=n_weeks,
            benchmark_type=benchmark.benchmark_type.value,
            benchmark_n=benchmark.n,
            mixed_promotion_comparison=mixed,
            distribution_primary_lever=dist_primary,
            outlier_flags=outliers,
            limitations=limitations,
            methodology=methodology,
            period=period,
            opportunity_label=config.opportunity_label,
        )
    return Evaluation(recommendation, signal, opportunity, limitations)
