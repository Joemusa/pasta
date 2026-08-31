"""Orchestrate canonical load → promo/non-promo split → directional tests."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import pandas as pd

from backend.agents.promotion.aggregations import aggregate_opportunities
from backend.agents.promotion.evaluate import QUANTIFIED, attach_derived, evaluate_grain
from backend.agents.promotion.loader import PromotionLoadError, load_integrated_unilever
from backend.agents.promotion.models import (
    DEFAULT_CONFIG_PATH,
    PROMOTION_AGENT_VERSION,
    V1_LIMITATIONS,
    PrimaryLever,
    PromotionAgentStatus,
    PromotionConfig,
    PromotionReport,
    Recommendation,
    load_promotion_config,
)
from backend.agents.promotion.overlap import load_overlap_index

logger = logging.getLogger("backend.agents.promotion")


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
    subsidising: int,
    overlap: int,
    intensity_baseline: int,
) -> list[str]:
    notes = [
        "Promotion Agent V1 produces estimated promotional opportunity, not causal incrementality.",
        *V1_LIMITATIONS,
        "A promoted SKU with higher volume is never sufficient on its own to claim incremental sales.",
        "Low distribution plus low sales is flagged as DISTRIBUTION FIRST instead of a promotion.",
        "26 July is kept as history where POS exists; that week has no dedicated price/promo extract.",
        "Commercial Brain is not built in this sprint; overlap flags are not combined into one opportunity.",
    ]
    notes.append(f"Period list in this run: {', '.join(periods) if periods else 'none'}.")
    notes.append(f"Current-period grains evaluated: {evaluated}.")
    if insufficient:
        notes.append(f"{insufficient} grain(s) were INSUFFICIENT EVIDENCE.")
    if distribution_primary:
        notes.append(f"{distribution_primary} emitted row(s) carry the distribution-primary flag.")
    if subsidising:
        notes.append(f"{subsidising} emitted row(s) may be subsidising existing demand.")
    if overlap:
        notes.append(f"{overlap} emitted row(s) overlap a Price or Distribution opportunity.")
    if intensity_baseline:
        notes.append(
            f"{intensity_baseline} emitted row(s) used low promo-intensity as the baseline "
            "because a true non-promo group was not available."
        )
    if opportunities == 0:
        notes.append("No SKU x retailer x region unit met the evidence bar for a quantified promotional test.")
    return notes


def _status(evaluated: int) -> PromotionAgentStatus:
    if evaluated == 0:
        return PromotionAgentStatus.NOT_READY
    return PromotionAgentStatus.READY_WITH_WARNINGS


def _default_data_root(source: Path) -> Path:
    if source.parent.name == "integrated":
        return source.parent.parent
    return Path("backend/data").resolve()


def run_promotion(
    input_path: str | Path,
    *,
    data_root: str | Path | None = None,
    config_path: str | Path | None = None,
    write_outputs: bool = True,
) -> PromotionReport:
    _configure_logging()
    source_input = Path(input_path).expanduser().resolve()
    config: PromotionConfig = load_promotion_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    logger.info("promotion_start input=%s manufacturer=%s", source_input, config.manufacturer)
    source, frame = load_integrated_unilever(source_input, config)
    if frame.empty:
        raise PromotionLoadError(f"No {config.manufacturer} POS rows in integrated source {source}")
    frame = attach_derived(frame, config)
    valid_dates = frame["date"].dropna()
    if valid_dates.empty:
        raise PromotionLoadError("Integrated Unilever data has no valid dates")
    current_period = valid_dates.max()
    current = frame.loc[frame["date"] == current_period].copy()
    product_map: dict[str, pd.DataFrame] = {}
    for product, group in frame.groupby("product", dropna=False, sort=False):
        product_map[str(product)] = group.sort_values("date")

    root = Path(data_root).expanduser().resolve() if data_root else _default_data_root(source)
    stem = source.name.removesuffix(".commercial.csv").removesuffix(".csv")
    overlap = load_overlap_index(root, stem)

    opportunities = []
    rec_counts: dict[str, int] = defaultdict(int)
    evaluated = 0
    dist_primary_emitted = 0
    subsidising_emitted = 0
    overlap_emitted = 0
    intensity_baseline_emitted = 0
    lever_counts = {item.value: 0 for item in PrimaryLever}
    uplift_summary = {
        "positive_volume_uplift": 0,
        "negative_volume_uplift": 0,
        "positive_value_uplift": 0,
        "negative_value_uplift": 0,
        "subsidising_existing_demand": 0,
        "normal_price_unavailable": 0,
        "promotion_type_unavailable": 0,
    }

    for row in current.itertuples(index=False):
        product = None if pd.isna(row.product) else str(row.product).strip()
        retailer = None if pd.isna(row.retailer) else str(row.retailer).strip()
        region = None if pd.isna(row.region) else str(row.region).strip()
        if not product or not retailer or not region:
            rec_counts[Recommendation.INSUFFICIENT_EVIDENCE.value] += 1
            continue
        evaluated += 1
        history = product_map.get(product, current.iloc[0:0])
        series = current.loc[
            (current["product"] == product) & (current["retailer"] == retailer) & (current["region"] == region)
        ].iloc[0]
        result = evaluate_grain(
            row=series,
            current=current,
            product_history=history,
            current_date=current_period,
            config=config,
            overlap=overlap,
        )
        rec_counts[result.recommendation.value] += 1
        lever_counts[result.primary_lever.value] = lever_counts.get(result.primary_lever.value, 0) + 1
        if result.opportunity is not None:
            opportunities.append(result.opportunity)
            if result.opportunity.distribution_primary_lever:
                dist_primary_emitted += 1
            if result.opportunity.subsidising_existing_demand:
                subsidising_emitted += 1
            if result.opportunity.overlaps_price_opportunity or result.opportunity.overlaps_distribution_opportunity:
                overlap_emitted += 1
            if result.opportunity.baseline_kind == "low_promo_intensity":
                intensity_baseline_emitted += 1
            if result.opportunity.volume_uplift_pct is not None:
                if result.opportunity.volume_uplift_pct > 0:
                    uplift_summary["positive_volume_uplift"] += 1
                elif result.opportunity.volume_uplift_pct < 0:
                    uplift_summary["negative_volume_uplift"] += 1
            if result.opportunity.value_uplift_pct is not None:
                if result.opportunity.value_uplift_pct > 0:
                    uplift_summary["positive_value_uplift"] += 1
                elif result.opportunity.value_uplift_pct < 0:
                    uplift_summary["negative_value_uplift"] += 1
            if result.opportunity.subsidising_existing_demand:
                uplift_summary["subsidising_existing_demand"] += 1
            uplift_summary["normal_price_unavailable"] += 1
            uplift_summary["promotion_type_unavailable"] += 1

    quantified = [
        item
        for item in opportunities
        if item.recommendation in {rec.value for rec in QUANTIFIED} and item.estimated_incremental_value > 0
    ]
    quantified.sort(
        key=lambda item: (
            -item.estimated_incremental_value,
            -item.estimated_incremental_volume,
            item.product,
            item.retailer,
            item.region,
        )
    )
    risks = [
        item
        for item in opportunities
        if item.recommendation
        in {Recommendation.REDUCE_PROMOTION.value, Recommendation.DO_NOT_PROMOTE.value}
        or item.subsidising_existing_demand
    ]
    risks.sort(
        key=lambda item: (
            -abs(item.volume_uplift_pct or 0.0),
            item.product,
        )
    )
    top_retailers, top_skus, top_regions = aggregate_opportunities(quantified)
    top_n = config.output_top_n
    top_opp_n = config.output_top_opportunities
    period_list = sorted({ts.strftime("%Y-%m-%d") for ts in valid_dates})
    conf_dist = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in quantified:
        conf_dist[item.confidence] = conf_dist.get(item.confidence, 0) + 1
    top_slice = quantified[:top_opp_n]
    outlier_top = sum(1 for item in top_slice if item.outlier_flag)
    insufficient = rec_counts.get(Recommendation.INSUFFICIENT_EVIDENCE.value, 0)
    status = _status(evaluated)
    report = PromotionReport(
        status=status,
        version=PROMOTION_AGENT_VERSION,
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
        opportunities_emitted=len(quantified),
        recommendation_counts=dict(rec_counts),
        promotion_uplift_summary=uplift_summary,
        promotion_investment_priorities=top_retailers[:top_n],
        promotion_risks=risks[:top_n],
        total_incremental_value=round(sum(item.estimated_incremental_value for item in quantified), 2),
        total_incremental_volume=round(sum(item.estimated_incremental_volume for item in quantified), 4),
        confidence_distribution=conf_dist,
        distribution_primary_count=lever_counts.get(PrimaryLever.DISTRIBUTION.value, 0),
        price_primary_count=lever_counts.get(PrimaryLever.PRICE.value, 0),
        promotion_primary_count=lever_counts.get(PrimaryLever.PROMOTION.value, 0),
        overlap_flag_count=overlap_emitted,
        outlier_dependent_top_opportunities=outlier_top,
        top_promotional_opportunities=top_slice,
        top_retailers=top_retailers[:top_n],
        top_skus=top_skus[:top_n],
        top_regions=top_regions[:top_n],
        opportunities=quantified,
        limitations=_limitations(
            periods=period_list,
            evaluated=evaluated,
            opportunities=len(quantified),
            insufficient=insufficient,
            distribution_primary=dist_primary_emitted,
            subsidising=subsidising_emitted,
            overlap=overlap_emitted,
            intensity_baseline=intensity_baseline_emitted,
        ),
    )
    if write_outputs:
        reports_dir = root / "promotion_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"{stem}.promotion.json"
        report.report_output_path = _display_path(out_path)
        out_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
        logger.info(
            "promotion_written path=%s opportunities=%s value=%s",
            out_path,
            len(quantified),
            report.total_incremental_value,
        )
    return report
