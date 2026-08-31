"""Orchestrate canonical load → promotion control → benchmarks → directional tests."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import pandas as pd

from backend.agents.price.aggregations import aggregate_opportunities
from backend.agents.price.evaluate import attach_derived, evaluate_grain
from backend.agents.price.loader import PriceLoadError, load_integrated_unilever
from backend.agents.price.models import (
    DEFAULT_CONFIG_PATH,
    PriceAgentStatus,
    PriceConfig,
    PriceReport,
    Recommendation,
    load_price_config,
)

logger = logging.getLogger("backend.agents.price")


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


def _limitations(
    *,
    periods: list[str],
    evaluated: int,
    opportunities: int,
    insufficient: int,
    distribution_primary: int,
    mixed: int,
) -> list[str]:
    notes = [
        "Price Agent V1 produces directional price insights and estimated price-test opportunities, "
        "not causal elasticity or guaranteed incremental sales.",
        "off_promo_rsp / on_promo_rsp is not treated as normal shelf price.",
        "Promotion Indicator 0/1 in the source extract is a stacked state, not a grain-level promo flag.",
        "Missing promotion metrics are not converted to zero; uncontrolled promo blocks price-change tests.",
        "A lower price with higher volume/store is never sufficient on its own to recommend a price cut.",
        "Low distribution plus low sales is flagged as 'Distribution likely primary lever' instead of a price cut.",
    ]
    if len(periods) < 12:
        notes.append(
            f"Only {len(periods)} Unilever POS week(s) are in the canonical table; overlapping price/promo "
            "coverage is shorter still, and 4 Weeks CY fields may be rolling."
        )
    notes.append("26 July is kept as history where POS price exists; that week has no dedicated price/promo extract.")
    notes.append("Product names can map to multiple ProductsID values; SKU identity is the product name.")
    notes.append(f"Current-period grains evaluated: {evaluated}.")
    if insufficient:
        notes.append(f"{insufficient} grain(s) were INSUFFICIENT EVIDENCE.")
    if distribution_primary:
        notes.append(f"{distribution_primary} emitted row(s) carry the distribution-primary flag.")
    if mixed:
        notes.append(f"{mixed} emitted row(s) used a mixed or uncontrolled promotion comparison.")
    if opportunities == 0:
        notes.append("No SKU x retailer x region unit met the evidence bar for a quantified price test.")
    notes.append("Promotion Agent and Commercial Brain are not built in this sprint.")
    return notes


def _status(evaluated: int) -> PriceAgentStatus:
    if evaluated == 0:
        return PriceAgentStatus.NOT_READY
    return PriceAgentStatus.READY_WITH_WARNINGS


def _default_data_root(source: Path) -> Path:
    if source.parent.name == "integrated":
        return source.parent.parent
    return Path("backend/data").resolve()


def run_price(
    input_path: str | Path,
    *,
    data_root: str | Path | None = None,
    config_path: str | Path | None = None,
    write_outputs: bool = True,
) -> PriceReport:
    _configure_logging()
    source_input = Path(input_path).expanduser().resolve()
    config: PriceConfig = load_price_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    logger.info("price_start input=%s manufacturer=%s", source_input, config.manufacturer)
    source, frame = load_integrated_unilever(source_input, config)
    if frame.empty:
        raise PriceLoadError(f"No {config.manufacturer} POS rows in integrated source {source}")
    frame = attach_derived(frame, config)
    valid_dates = frame["date"].dropna()
    if valid_dates.empty:
        raise PriceLoadError("Integrated Unilever data has no valid dates")
    current_period = valid_dates.max()
    current = frame.loc[frame["date"] == current_period].copy()
    history_map: dict[tuple[str, str, str], pd.DataFrame] = {}
    for key, group in frame.groupby(["product", "retailer", "region"], dropna=False, sort=False):
        product, retailer, region = key
        history_map[(str(product), str(retailer), str(region))] = group.sort_values("date")

    opportunities = []
    rec_counts: dict[str, int] = defaultdict(int)
    signal_counts: dict[str, int] = defaultdict(int)
    evaluated = 0
    dist_primary_emitted = 0
    mixed_emitted = 0

    for row in current.itertuples(index=False):
        product = None if pd.isna(row.product) else str(row.product).strip()
        retailer = None if pd.isna(row.retailer) else str(row.retailer).strip()
        region = None if pd.isna(row.region) else str(row.region).strip()
        if not product or not retailer or not region:
            rec_counts[Recommendation.INSUFFICIENT_EVIDENCE.value] += 1
            continue
        evaluated += 1
        history = history_map.get((product, retailer, region), current.iloc[0:0])
        series = current.loc[
            (current["product"] == product) & (current["retailer"] == retailer) & (current["region"] == region)
        ].iloc[0]
        result = evaluate_grain(
            row=series,
            current=current,
            history=history,
            current_date=current_period,
            config=config,
        )
        rec_counts[result.recommendation.value] += 1
        signal_counts[result.signal.value] += 1
        if result.opportunity is not None:
            opportunities.append(result.opportunity)
            if result.opportunity.distribution_primary_lever:
                dist_primary_emitted += 1
            if result.opportunity.mixed_promotion_comparison:
                mixed_emitted += 1

    opportunities.sort(
        key=lambda item: (
            -item.estimated_value_opportunity,
            -item.estimated_volume_opportunity,
            item.product,
        )
    )
    top_retailers, top_skus, top_regions = aggregate_opportunities(opportunities)
    top_n = config.output_top_n
    period_list = sorted({ts.strftime("%Y-%m-%d") for ts in valid_dates})
    conf_dist = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in opportunities:
        conf_dist[item.confidence] = conf_dist.get(item.confidence, 0) + 1

    root = Path(data_root).expanduser().resolve() if data_root else _default_data_root(source)
    insufficient = rec_counts.get(Recommendation.INSUFFICIENT_EVIDENCE.value, 0)
    status = _status(evaluated)
    report = PriceReport(
        status=status,
        opportunity_label=config.opportunity_label,
        manufacturer=config.manufacturer,
        current_period=current_period.strftime("%Y-%m-%d"),
        source_integrated_file=_display_path(source),
        input_path=_display_path(source_input),
        periods_observed=len(period_list),
        period_list=period_list,
        unilever_rows=len(frame),
        current_period_rows=len(current),
        evaluated_grains=evaluated,
        opportunities_emitted=len(opportunities),
        recommendation_counts=dict(rec_counts),
        price_signal_summary=dict(signal_counts),
        total_value_opportunity=round(sum(item.estimated_value_opportunity for item in opportunities), 2),
        total_volume_opportunity=round(sum(item.estimated_volume_opportunity for item in opportunities), 4),
        confidence_distribution=conf_dist,
        top_price_opportunities=opportunities[:top_n],
        top_retailers=top_retailers[:top_n],
        top_skus=top_skus[:top_n],
        top_regions=top_regions[:top_n],
        opportunities=opportunities,
        limitations=_limitations(
            periods=period_list,
            evaluated=evaluated,
            opportunities=len(opportunities),
            insufficient=insufficient,
            distribution_primary=dist_primary_emitted,
            mixed=mixed_emitted,
        ),
    )
    if write_outputs:
        reports_dir = root / "price_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        stem = source.name.removesuffix(".commercial.csv").removesuffix(".csv")
        out_path = reports_dir / f"{stem}.price.json"
        report.report_output_path = _display_path(out_path)
        out_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
        logger.info(
            "price_written path=%s opportunities=%s value=%s",
            out_path,
            len(opportunities),
            report.total_value_opportunity,
        )
    return report
