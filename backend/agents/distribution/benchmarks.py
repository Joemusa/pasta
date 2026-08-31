"""Compare historical and peer store benchmarks and pick the most defensible one."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.agents.distribution.metrics import round_stores
from backend.agents.distribution.models import BenchmarkSnapshot, BenchmarkType, Confidence, DistributionConfig
from backend.agents.distribution.outliers import is_peak_spike


@dataclass(frozen=True)
class BenchmarkCandidate:
    benchmark_type: str
    benchmark_stores: float
    benchmark_confidence: Confidence
    defensibility: float


@dataclass
class UnitHistory:
    dates: list[pd.Timestamp]
    store_counts: list[float]
    sales_values: list[float]
    sales_volumes: list[float]


def _stat(values: list[float], statistic: str) -> float | None:
    if not values:
        return None
    series = pd.Series(values, dtype="float64")
    if statistic == "mean":
        return float(series.mean())
    if statistic in {"p75", "quantile_75"}:
        return float(series.quantile(0.75))
    return float(series.median())


def _confidence_from_n(n: int, config: DistributionConfig, *, high_ok: bool) -> Confidence:
    if high_ok and n >= config.min_history_for_high_confidence:
        return "HIGH"
    if n >= config.min_history_for_medium_confidence:
        return "MEDIUM"
    return "LOW"


def historical_metrics(
    history: UnitHistory,
    current_date: pd.Timestamp,
    config: DistributionConfig,
) -> dict[str, float | int | bool | None]:
    stores = history.store_counts
    n = len(stores)
    peak = max(stores) if stores else None
    average = float(pd.Series(stores, dtype="float64").mean()) if stores else None
    ordered = sorted(zip(history.dates, stores, strict=True), key=lambda item: item[0])
    recent = ordered[-config.recent_periods :] if ordered else []
    recent_high = max(value for _, value in recent) if recent else None
    spike = is_peak_spike(stores, config) if stores else False
    return {
        "n_periods": n,
        "historical_peak": peak,
        "historical_average": average,
        "recent_high": recent_high,
        "peak_is_spike": spike,
        "current_is_latest": bool(ordered and ordered[-1][0] == current_date),
    }


def peer_store_counts(
    current: pd.DataFrame,
    sku: str,
    retailer: str,
    region: str,
    *,
    kind: str,
    config: DistributionConfig,
    current_stores: float,
) -> list[float]:
    if kind == "retailer":
        peers = current[(current["sku"] == sku) & (current["retailer"] == retailer) & (current["region"] != region)]
    else:
        peers = current[(current["sku"] == sku) & (current["region"] == region) & (current["retailer"] != retailer)]
        if current_stores > 0:
            lo = current_stores / config.peer_scale_ratio
            hi = current_stores * config.peer_scale_ratio
            peers = peers[peers["store_count"].between(lo, hi)]
    values = [float(v) for v in peers["store_count"].tolist() if pd.notna(v)]
    return values


def _candidate_from_level(
    *,
    benchmark_type: str,
    raw_stores: float | None,
    current_stores: float,
    n: int,
    config: DistributionConfig,
    defensibility: float,
    high_ok: bool,
    extra_penalty: float = 0.0,
) -> BenchmarkCandidate | None:
    if raw_stores is None:
        return None
    potential = round_stores(raw_stores)
    if potential - current_stores < config.min_store_gap:
        return None
    confidence = _confidence_from_n(n, config, high_ok=high_ok)
    return BenchmarkCandidate(
        benchmark_type=benchmark_type,
        benchmark_stores=potential,
        benchmark_confidence=confidence,
        defensibility=defensibility - extra_penalty,
    )


def consider_benchmarks(
    *,
    current_stores: float,
    history: UnitHistory,
    current_date: pd.Timestamp,
    retailer_peers: list[float],
    regional_peers: list[float],
    config: DistributionConfig,
) -> tuple[BenchmarkCandidate | None, dict[str, BenchmarkSnapshot], bool]:
    hist = historical_metrics(history, current_date, config)
    n_hist = int(hist["n_periods"] or 0)
    peak = hist["historical_peak"]
    average = hist["historical_average"]
    recent_high = hist["recent_high"]
    spike = bool(hist["peak_is_spike"])

    snapshots: dict[str, BenchmarkSnapshot] = {
        BenchmarkType.HISTORICAL_PEAK.value: BenchmarkSnapshot(
            stores=None if peak is None else float(peak),
            available=peak is not None,
            flagged_spike=spike,
            observations=n_hist,
        ),
        BenchmarkType.HISTORICAL_AVERAGE.value: BenchmarkSnapshot(
            stores=None if average is None else float(average),
            available=average is not None,
            observations=n_hist,
        ),
        BenchmarkType.RECENT_HIGH.value: BenchmarkSnapshot(
            stores=None if recent_high is None else float(recent_high),
            available=recent_high is not None,
            flagged_spike=bool(spike and recent_high is not None and peak is not None and recent_high == peak),
            observations=min(n_hist, config.recent_periods),
        ),
        BenchmarkType.RETAILER_PEER.value: BenchmarkSnapshot(
            stores=_stat(retailer_peers, config.peer_statistic),
            available=len(retailer_peers) >= config.min_peer_observations,
            observations=len(retailer_peers),
        ),
        BenchmarkType.REGIONAL_PEER.value: BenchmarkSnapshot(
            stores=_stat(regional_peers, config.peer_statistic),
            available=len(regional_peers) >= config.min_peer_observations,
            observations=len(regional_peers),
        ),
    }

    candidates: list[BenchmarkCandidate] = []

    recent_is_spike = snapshots[BenchmarkType.RECENT_HIGH.value].flagged_spike
    if not recent_is_spike:
        cand = _candidate_from_level(
            benchmark_type=BenchmarkType.RECENT_HIGH.value,
            raw_stores=recent_high if isinstance(recent_high, (int, float)) else None,
            current_stores=current_stores,
            n=n_hist,
            config=config,
            defensibility=80.0,
            high_ok=True,
        )
        if cand:
            candidates.append(cand)

    cand = _candidate_from_level(
        benchmark_type=BenchmarkType.HISTORICAL_AVERAGE.value,
        raw_stores=average if isinstance(average, (int, float)) else None,
        current_stores=current_stores,
        n=n_hist,
        config=config,
        defensibility=70.0,
        high_ok=True,
    )
    if cand:
        candidates.append(cand)

    if snapshots[BenchmarkType.RETAILER_PEER.value].available:
        cand = _candidate_from_level(
            benchmark_type=BenchmarkType.RETAILER_PEER.value,
            raw_stores=snapshots[BenchmarkType.RETAILER_PEER.value].stores,
            current_stores=current_stores,
            n=len(retailer_peers),
            config=config,
            defensibility=75.0 if len(retailer_peers) >= 5 else 60.0,
            high_ok=len(retailer_peers) >= 5,
        )
        if cand:
            candidates.append(cand)

    if snapshots[BenchmarkType.REGIONAL_PEER.value].available:
        cand = _candidate_from_level(
            benchmark_type=BenchmarkType.REGIONAL_PEER.value,
            raw_stores=snapshots[BenchmarkType.REGIONAL_PEER.value].stores,
            current_stores=current_stores,
            n=len(regional_peers),
            config=config,
            defensibility=50.0 if len(regional_peers) >= 5 else 40.0,
            high_ok=False,
            extra_penalty=5.0,
        )
        if cand:
            candidates.append(cand)

    if not spike:
        peak_repeat = 0 if peak is None else history.store_counts.count(float(peak))
        cand = _candidate_from_level(
            benchmark_type=BenchmarkType.HISTORICAL_PEAK.value,
            raw_stores=peak if isinstance(peak, (int, float)) else None,
            current_stores=current_stores,
            n=n_hist,
            config=config,
            defensibility=65.0 if peak_repeat >= 2 else 50.0,
            high_ok=peak_repeat >= 2,
        )
        if cand:
            candidates.append(cand)

    if not candidates:
        return None, snapshots, spike

    candidates.sort(key=lambda item: (-item.defensibility, item.benchmark_stores, item.benchmark_type))
    chosen = candidates[0]
    snapshots[chosen.benchmark_type] = snapshots[chosen.benchmark_type].model_copy(update={"selected": True})
    return chosen, snapshots, spike
