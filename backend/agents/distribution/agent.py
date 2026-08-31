"""Orchestrate clean-load → current period → benchmarks → opportunities → roll-ups."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import pandas as pd

from backend.agents.distribution.aggregations import aggregate_opportunities
from backend.agents.distribution.benchmarks import UnitHistory, consider_benchmarks, peer_store_counts
from backend.agents.distribution.confidence import assign_confidence
from backend.agents.distribution.loader import DistributionLoadError, load_manufacturer_clean
from backend.agents.distribution.metrics import (
    distribution_gap,
    value_opportunity,
    value_per_store,
    volume_opportunity,
    volume_per_store,
)
from backend.agents.distribution.models import (
    DEFAULT_CONFIG_PATH,
    DistributionConfig,
    DistributionReport,
    Opportunity,
    load_distribution_config,
)
from backend.agents.distribution.outliers import mad_outlier_mask

logger = logging.getLogger("backend.agents.distribution")


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _history_map(frame: pd.DataFrame) -> dict[tuple[str, str, str], UnitHistory]:
    grouped: dict[tuple[str, str, str], UnitHistory] = {}
    for (sku, retailer, region), group in frame.groupby(["sku", "retailer", "region"], dropna=False, sort=False):
        ordered = group.sort_values("date")
        grouped[(str(sku), str(retailer), str(region))] = UnitHistory(
            dates=list(ordered["date"]),
            store_counts=[float(v) if pd.notna(v) else 0.0 for v in ordered["store_count"]],
            sales_values=[float(v) if pd.notna(v) else float("nan") for v in ordered["sales_value"]],
            sales_volumes=[float(v) if pd.notna(v) else float("nan") for v in ordered["sales_volume"]],
        )
    return grouped


def _imputed_rates(
    history: UnitHistory,
    retailer_peers: pd.DataFrame,
    regional_peers: pd.DataFrame,
) -> tuple[float | None, float | None, bool]:
    own_vps: list[float] = []
    own_vol: list[float] = []
    for stores, value, volume in zip(history.store_counts, history.sales_values, history.sales_volumes, strict=True):
        rate_v = value_per_store(value, stores)
        rate_q = volume_per_store(volume, stores)
        if rate_v is not None:
            own_vps.append(rate_v)
        if rate_q is not None:
            own_vol.append(rate_q)
    if own_vps and own_vol:
        return float(pd.Series(own_vps).median()), float(pd.Series(own_vol).median()), True

    def peer_rates(peers: pd.DataFrame) -> tuple[float | None, float | None]:
        if peers.empty:
            return None, None
        vps = [
            value_per_store(float(row.sales_value), float(row.store_count))
            for row in peers.itertuples(index=False)
            if pd.notna(row.sales_value) and pd.notna(row.store_count)
        ]
        vol = [
            volume_per_store(float(row.sales_volume), float(row.store_count))
            for row in peers.itertuples(index=False)
            if pd.notna(row.sales_volume) and pd.notna(row.store_count)
        ]
        vps_f = [v for v in vps if v is not None]
        vol_f = [v for v in vol if v is not None]
        return (
            float(pd.Series(vps_f).median()) if vps_f else None,
            float(pd.Series(vol_f).median()) if vol_f else None,
        )

    value_rate, volume_rate = peer_rates(retailer_peers)
    if value_rate is None or volume_rate is None:
        value_rate, volume_rate = peer_rates(regional_peers)
    if value_rate is None or volume_rate is None:
        return None, None, True
    return value_rate, volume_rate, True


def _limitations(
    *,
    identity: str,
    periods: list[str],
    skipped_missing: int,
    skipped_no_rate: int,
    flagged: int,
    current_period_rows: int,
    opportunities: int,
) -> list[str]:
    notes = [
        "Figures are an estimated distribution opportunity, not guaranteed incremental sales.",
        "Current metrics use a single reporting period and are not mixed with other dates.",
        "Historical peak store count is not used automatically; spiked peaks are flagged and skipped.",
    ]
    if identity == "product":
        notes.append("SKU identity is the product name because the cleaned file has no sku column.")
    if len(periods) < 8:
        notes.append(
            f"Only {len(periods)} populated period(s) are available in the cleaned Unilever extract; "
            "benchmarks are therefore thinner than a full history."
        )
    if skipped_missing:
        notes.append(f"{skipped_missing} current-period row(s) were skipped because required fields were missing.")
    if skipped_no_rate:
        notes.append(f"{skipped_no_rate} unit(s) had a store gap but no defensible value/volume per store rate.")
    if flagged:
        notes.append(f"{flagged} opportunity(ies) carry outlier flags; outliers were kept, not deleted.")
    if opportunities == 0:
        notes.append("No SKU x retailer x region unit had a defensible store gap of at least one store.")
    notes.append(f"Current-period Unilever grain rows analysed: {current_period_rows}.")
    return notes


def run_distribution(
    input_path: str | Path,
    *,
    data_root: str | Path | None = None,
    config_path: str | Path | None = None,
    write_outputs: bool = True,
) -> DistributionReport:
    """Run the Distribution Agent on a cleaned POS extract or a clean/ directory."""
    _configure_logging()
    source_input = Path(input_path).expanduser().resolve()
    config: DistributionConfig = load_distribution_config(
        Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    )
    logger.info("distribution_start input=%s manufacturer=%s", source_input, config.manufacturer)
    source, frame, identity = load_manufacturer_clean(source_input, config)
    if frame.empty:
        raise DistributionLoadError(f"No {config.manufacturer} rows in cleaned source {source}")

    valid_dates = frame["date"].dropna()
    if valid_dates.empty:
        raise DistributionLoadError("Cleaned Unilever data has no valid dates")
    current_period = valid_dates.max()
    current = frame.loc[frame["date"] == current_period].copy()
    history_by_grain = _history_map(frame.dropna(subset=["sku", "retailer", "region"]))

    opportunities: list[Opportunity] = []
    skipped_missing = 0
    skipped_no_gap = 0
    skipped_no_rate = 0
    current_sales: dict[tuple[str, str], float] = defaultdict(float)

    for row in current.itertuples(index=False):
        sku = row.sku if pd.notna(row.sku) and str(row.sku).strip() else None
        retailer = row.retailer if pd.notna(row.retailer) and str(row.retailer).strip() else None
        region = row.region if pd.notna(row.region) and str(row.region).strip() else None
        stores = float(row.store_count) if pd.notna(row.store_count) else None
        sales_value = float(row.sales_value) if pd.notna(row.sales_value) else None
        sales_volume = float(row.sales_volume) if pd.notna(row.sales_volume) else None
        if sku is None or retailer is None or region is None or stores is None:
            skipped_missing += 1
            continue
        if sales_value is not None:
            current_sales[("retailer", retailer)] += sales_value
            current_sales[("region", region)] += sales_value
            current_sales[("sku", sku)] += sales_value

        history = history_by_grain.get((sku, retailer, region), UnitHistory([], [], [], []))
        retailer_peer_values = peer_store_counts(
            current, sku, retailer, region, kind="retailer", config=config, current_stores=stores
        )
        regional_peer_values = peer_store_counts(
            current, sku, retailer, region, kind="region", config=config, current_stores=stores
        )
        chosen, snapshots, spike = consider_benchmarks(
            current_stores=stores,
            history=history,
            current_date=current_period,
            retailer_peers=retailer_peer_values,
            regional_peers=regional_peer_values,
            config=config,
        )
        if chosen is None:
            skipped_no_gap += 1
            continue

        gap = distribution_gap(stores, chosen.benchmark_stores)
        if gap is None or gap < config.min_store_gap:
            skipped_no_gap += 1
            continue

        vps = value_per_store(sales_value, stores)
        volps = volume_per_store(sales_volume, stores)
        rate_imputed = False
        outlier_flags: list[str] = []
        if spike:
            outlier_flags.append("historical_peak_spike")

        hist_vps: list[float] = []
        hist_vol: list[float] = []
        for hist_stores, hist_value, hist_volume in zip(
            history.store_counts, history.sales_values, history.sales_volumes, strict=True
        ):
            rate_v = value_per_store(hist_value, hist_stores)
            rate_q = volume_per_store(hist_volume, hist_stores)
            if rate_v is not None:
                hist_vps.append(rate_v)
            if rate_q is not None:
                hist_vol.append(rate_q)
        if hist_vps and len(hist_vps) >= 3:
            mask = mad_outlier_mask(pd.Series(hist_vps), config.mad_threshold)
            if bool(mask.iloc[-1]) and vps is not None:
                outlier_flags.append("value_per_store_outlier")
                vps = float(pd.Series(hist_vps).median())
                rate_imputed = True
        if stores <= 0 or vps is None or volps is None:
            retailer_peer_rows = current[
                (current["sku"] == sku) & (current["retailer"] == retailer) & (current["region"] != region)
            ]
            regional_peer_rows = current[
                (current["sku"] == sku) & (current["region"] == region) & (current["retailer"] != retailer)
            ]
            vps_i, vol_i, rate_imputed = _imputed_rates(history, retailer_peer_rows, regional_peer_rows)
            vps = vps if vps is not None else vps_i
            volps = volps if volps is not None else vol_i
        if vps is None or volps is None:
            skipped_no_rate += 1
            continue

        value_opp = value_opportunity(gap, vps)
        volume_opp = volume_opportunity(gap, volps)
        if value_opp is None or volume_opp is None:
            skipped_no_rate += 1
            continue

        confidence = assign_confidence(
            n_periods=len(history.store_counts),
            current_stores=stores,
            benchmark_type=chosen.benchmark_type,
            benchmark_confidence=chosen.benchmark_confidence,
            value_per_store_history=hist_vps,
            outlier_flags=outlier_flags,
            rate_is_imputed=rate_imputed,
            config=config,
        )
        period_str = current_period.strftime("%Y-%m-%d")
        opportunity_id = f"{period_str}|{sku}|{retailer}|{region}"
        opportunities.append(
            Opportunity(
                opportunity_id=opportunity_id,
                sku=sku,
                retailer=retailer,
                region=region,
                current_stores=round(stores, 4),
                benchmark_stores=round(chosen.benchmark_stores, 4),
                store_gap=round(gap, 4),
                value_per_store=round(vps, 4),
                volume_per_store=round(volps, 4),
                value_opportunity=round(value_opp, 2),
                volume_opportunity=round(volume_opp, 4),
                benchmark_type=chosen.benchmark_type,
                confidence=confidence,
                period=period_str,
                benchmark_confidence=chosen.benchmark_confidence,
                outlier_flags=outlier_flags,
                benchmarks_considered=snapshots,
                sku_identity_field=identity,
            )
        )

    opportunities.sort(
        key=lambda item: (-item.value_opportunity, -item.volume_opportunity, -item.store_gap, item.sku)
    )
    top_retailers, top_regions, top_skus = aggregate_opportunities(opportunities, current_sales)
    top_n = config.output_top_n
    period_list = sorted({ts.strftime("%Y-%m-%d") for ts in valid_dates})
    flagged = sum(1 for item in opportunities if item.outlier_flags)
    conf_dist = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in opportunities:
        conf_dist[item.confidence] = conf_dist.get(item.confidence, 0) + 1

    if data_root:
        root = Path(data_root).expanduser().resolve()
    elif source_input.is_dir() and source_input.name == "clean":
        root = source_input.parent
    elif source.parent.name == "clean":
        root = source.parent.parent
    else:
        root = Path("backend/data").resolve()
    reports_dir = root / "distribution_reports"

    report = DistributionReport(
        manufacturer=config.manufacturer,
        current_period=current_period.strftime("%Y-%m-%d"),
        sku_identity_field=identity,
        source_clean_file=_display_path(source),
        input_path=_display_path(source_input),
        periods_observed=len(period_list),
        period_list=period_list,
        unilever_rows=len(frame),
        current_period_rows=len(current),
        opportunities_emitted=len(opportunities),
        skipped_missing=skipped_missing,
        skipped_no_gap=skipped_no_gap,
        skipped_no_rate=skipped_no_rate,
        total_value_opportunity=round(sum(item.value_opportunity for item in opportunities), 2),
        total_volume_opportunity=round(sum(item.volume_opportunity for item in opportunities), 4),
        confidence_distribution=conf_dist,
        top_retailers=top_retailers[:top_n],
        top_regions=top_regions[:top_n],
        top_skus=top_skus[:top_n],
        top_opportunities=opportunities[:top_n],
        opportunities=opportunities,
        flagged_outlier_count=flagged,
        limitations=_limitations(
            identity=identity,
            periods=period_list,
            skipped_missing=skipped_missing,
            skipped_no_rate=skipped_no_rate,
            flagged=flagged,
            current_period_rows=len(current),
            opportunities=len(opportunities),
        ),
    )
    if write_outputs:
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"{source.stem.replace('.clean', '')}.distribution.json"
        report.report_output_path = _display_path(out_path)
        out_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
        logger.info(
            "distribution_written path=%s opportunities=%s value=%s",
            out_path,
            len(opportunities),
            report.total_value_opportunity,
        )
    return report
