"""Commercial Brain V1: specialist outputs → de-duplicated actions and one-slide narrative."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from backend.agents.brain.actions import (
    build_one_slide,
    build_story,
    core_headline,
    headline_support,
    select_top_actions,
)
from backend.agents.brain.aggregations import aggregate_movers, sku_priorities
from backend.agents.brain.levers import LeverDecision, decide_all
from backend.agents.brain.loader import BrainLoadError, SpecialistBundle, discover_bundle
from backend.agents.brain.models import (
    BRAIN_VERSION,
    DEFAULT_CONFIG_PATH,
    V1_LIMITATIONS,
    BrainAgentStatus,
    BrainConfig,
    BrainOpportunity,
    BrainReport,
    DominantLever,
    load_brain_config,
)
from backend.agents.brain.scoring import METHODOLOGY, priority_score

logger = logging.getLogger("backend.agents.brain")


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


def recommended_action_text(decision: LeverDecision) -> str:
    product = decision.product
    retailer = decision.retailer
    region = decision.region
    if decision.dominant == DominantLever.DISTRIBUTION and decision.dist is not None:
        gap = decision.dist.store_gap
        target = decision.dist.benchmark_stores
        extra = f" toward {target:.0f} stores" if target is not None else ""
        return (
            f"Brief a distribution expansion for {product} at {retailer} in {region}: close a "
            f"{gap:.0f}-store gap{extra}. Do not lead with a price cut because sales are low."
        )
    if decision.dominant == DominantLever.PROMOTION and decision.promo is not None:
        uplift = decision.promo.volume_uplift_pct
        uplift_txt = f" (directional uplift {uplift:.0%})" if uplift is not None else ""
        return (
            f"Run a {decision.promo.recommendation.lower()} for {product} at {retailer} in {region}{uplift_txt}. "
            f"Treat the result as a test, not booked incrementality."
        )
    if decision.dominant == DominantLever.PRICE and decision.price is not None:
        return (
            f"Run a {decision.price.recommendation.lower()} for {product} at {retailer} in {region} versus the "
            f"like-for-like benchmark. Do not discount solely because sales are low."
        )
    if decision.dominant == DominantLever.MULTI_LEVER and decision.dist is not None:
        return (
            f"Expand distribution of {product} at {retailer} in {region} and, once listed stores are in place, "
            f"support with a targeted promotion test. Do not add the two specialist values together."
        )
    return f"Do not brief a commercial test for {product} at {retailer} in {region}; evidence is insufficient."


def evidence_lines(decision: LeverDecision) -> list[str]:
    lines: list[str] = []
    if decision.dist is not None:
        lines.append(
            f"Distribution: store gap {decision.dist.store_gap:.1f}, "
            f"value/store {decision.dist.value_per_store}, confidence {decision.dist.confidence}, "
            f"estimated R{decision.dist.value:,.0f} / {decision.dist.volume:.1f} units."
        )
    if decision.price is not None:
        lines.append(
            f"Price: {decision.price.recommendation} ({decision.price.price_signal}), "
            f"confidence {decision.price.confidence}, estimated R{decision.price.value:,.0f} / "
            f"{decision.price.volume:.1f} units."
        )
    if decision.promo is not None:
        uplift = decision.promo.volume_uplift_pct
        uplift_txt = f", volume uplift {uplift:.0%}" if uplift is not None else ""
        lines.append(
            f"Promotion: {decision.promo.recommendation}{uplift_txt}, "
            f"confidence {decision.promo.confidence}, estimated R{decision.promo.value:,.0f} / "
            f"{decision.promo.volume:.1f} units."
        )
    lines.append(
        f"Primary lever value R{decision.primary_value:,.0f} / {decision.primary_volume:.1f} units "
        f"(gross specialist total R{decision.gross_value:,.0f} was not used)."
    )
    if decision.commercial is not None and decision.commercial.sales_value is not None:
        lines.append(f"Current sales R{decision.commercial.sales_value:,.0f} (not the opportunity).")
    lines.append(f"Double-counting risk: {decision.double_counting_risk.value}.")
    return lines


def to_opportunity(decision: LeverDecision, config: BrainConfig) -> BrainOpportunity:
    sales = decision.commercial.sales_value if decision.commercial else None
    volume = decision.commercial.sales_volume if decision.commercial else None
    stores = None
    vps = None
    valps = None
    gap = None
    if decision.dist is not None:
        stores = decision.dist.current_stores
        vps = decision.dist.volume_per_store
        valps = decision.dist.value_per_store
        gap = decision.dist.store_gap
    if stores is None and decision.commercial is not None:
        stores = decision.commercial.store_count
    if valps is None and decision.commercial is not None and sales is not None and stores:
        if stores > 0:
            valps = sales / stores
    if vps is None and decision.commercial is not None and volume is not None and stores:
        if stores > 0:
            vps = volume / stores
    price_signal = decision.price.price_signal if decision.price is not None else None
    promo_signal = decision.promo.recommendation if decision.promo is not None else None
    score = priority_score(decision, config)
    period_key = f"{decision.product}|{decision.retailer}|{decision.region}"
    return BrainOpportunity(
        opportunity_id=period_key,
        product=decision.product,
        brand=decision.brand,
        retailer=decision.retailer,
        region=decision.region,
        dominant_lever=decision.dominant.value,
        secondary_lever=None if decision.secondary is None else decision.secondary.value,
        overlap=decision.overlap,
        gross_estimated_value=decision.gross_value,
        gross_estimated_volume=decision.gross_volume,
        primary_lever_value=decision.primary_value,
        primary_lever_volume=decision.primary_volume,
        secondary_lever_value=decision.secondary_value,
        secondary_lever_volume=decision.secondary_volume,
        double_counting_risk=decision.double_counting_risk.value,
        opportunity_value=decision.primary_value,
        opportunity_volume=decision.primary_volume,
        current_sales=None if sales is None else round(sales, 2),
        current_volume=None if volume is None else round(volume, 4),
        sales_per_store=None if valps is None else round(valps, 4),
        volume_per_store=None if vps is None else round(vps, 4),
        distribution_stores=None if stores is None else round(stores, 4),
        distribution_gap=None if gap is None else round(gap, 4),
        price_signal=price_signal,
        promotion_signal=promo_signal,
        priority_score=score,
        confidence=decision.confidence,  # type: ignore[arg-type]
        recommended_action=recommended_action_text(decision),
        evidence=evidence_lines(decision),
        limitations=decision.limitations,
    )


def _status(actions: int, evaluated: int) -> BrainAgentStatus:
    if evaluated == 0 or actions == 0:
        return BrainAgentStatus.NOT_READY
    return BrainAgentStatus.READY_WITH_WARNINGS


def _risks(opportunities: list[BrainOpportunity], conflicts: int) -> list[str]:
    risks = [
        "Opportunity estimates are directional and are not guaranteed incremental sales.",
        "Price and promotion findings are not causal elasticity or causal incrementality.",
        "LOW-confidence specialist outputs are preserved; the Brain does not upgrade them.",
    ]
    if conflicts:
        risks.append(
            f"{conflicts} SKU x retailer x region grain(s) had overlapping specialist values that were not summed."
        )
    low = sum(1 for item in opportunities if item.confidence == "LOW")
    if low:
        risks.append(f"{low} prioritised grain(s) remain LOW confidence because of the short panel.")
    return risks


def _limitations(bundle: SpecialistBundle, evaluated: int, conflicts: int) -> list[str]:
    notes = [
        "Commercial Brain V1 converts frozen specialist outputs into a small set of actions. "
        "It does not re-run Data QA, Distribution, Price, or Promotion agents.",
        *V1_LIMITATIONS,
    ]
    notes.append(f"Period: {bundle.current_period or 'unknown'}.")
    notes.append(f"Grains with at least one specialist flag: {evaluated}.")
    notes.append(f"Double-counting conflicts resolved: {conflicts}.")
    notes.append("Dashboard, PDF, macroeconomic, and social-media layers are not built in this sprint.")
    return notes


def run_brain(
    input_path: str | Path,
    *,
    config_path: str | Path | None = None,
    write_outputs: bool = True,
) -> BrainReport:
    _configure_logging()
    source_input = Path(input_path).expanduser().resolve()
    config: BrainConfig = load_brain_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    logger.info("brain_start input=%s manufacturer=%s", source_input, config.manufacturer)
    bundle = discover_bundle(source_input)
    if not bundle.dist and not bundle.price and not bundle.promo:
        raise BrainLoadError("Specialist reports contain no opportunities")
    decisions = decide_all(
        dist=bundle.dist,
        price=bundle.price,
        promo=bundle.promo,
        commercial=bundle.commercial,
        config=config,
    )
    opportunities = [to_opportunity(item, config) for item in decisions]
    actionable = [
        item
        for item in opportunities
        if item.dominant_lever != DominantLever.INSUFFICIENT_EVIDENCE.value
        and item.opportunity_value >= config.min_primary_value
        and item.opportunity_volume >= 0
    ]
    actionable.sort(key=lambda item: (-item.priority_score, -item.opportunity_value, item.product))
    conflicts = sum(1 for item in decisions if item.specialist_count >= 2)
    lever_counts: dict[str, int] = defaultdict(int)
    conf_dist = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in actionable:
        lever_counts[item.dominant_lever] += 1
        conf_dist[item.confidence] = conf_dist.get(item.confidence, 0) + 1
    total_value = round(sum(item.opportunity_value for item in actionable), 2)
    total_volume = round(sum(item.opportunity_volume for item in actionable), 4)
    retailers, regions = aggregate_movers(actionable)
    top_n = config.output_top_n
    skus = sku_priorities(actionable, top_n)
    actions = select_top_actions(actionable, config)
    top_region = regions[0].name if regions else None
    headline = core_headline(actionable, actions, top_region)
    story = build_story(
        headline=headline,
        actions=actions,
        total_value=total_value,
        total_volume=total_volume,
    )
    support = headline_support(story, actions)
    coverage = (
        f"Specialist stems '{bundle.stem}'; current period {bundle.current_period}; "
        f"{len(bundle.dist)} distribution, {len(bundle.price)} price, {len(bundle.promo)} promotion flags; "
        f"canonical commercial rows {'present' if bundle.commercial else 'absent'}."
    )
    risks = _risks(actionable, conflicts)
    limitations = _limitations(bundle, len(decisions), conflicts)
    one_slide = build_one_slide(
        headline=headline,
        support=support,
        total_value=total_value,
        total_volume=total_volume,
        actions=actions,
        retailers=[item.model_dump(mode="json") for item in retailers[:top_n]],
        skus=[item.model_dump(mode="json") for item in skus[:top_n]],
        regions=[item.model_dump(mode="json") for item in regions[:top_n]],
        risks=risks,
        limitations=limitations,
        methodology=METHODOLOGY,
        data_coverage=coverage,
    )
    status = _status(len(actions), len(decisions))
    report = BrainReport(
        status=status,
        version=BRAIN_VERSION,
        manufacturer=config.manufacturer,
        current_period=bundle.current_period or "",
        source_distribution_report=_display_path(bundle.distribution_path),
        source_price_report=_display_path(bundle.price_path),
        source_promotion_report=_display_path(bundle.promotion_path),
        source_integrated_file=None if bundle.commercial_path is None else _display_path(bundle.commercial_path),
        input_path=_display_path(source_input),
        grains_evaluated=len(decisions),
        opportunities_emitted=len(actionable),
        double_counting_conflicts_resolved=conflicts,
        lever_distribution=dict(lever_counts),
        confidence_distribution=conf_dist,
        total_estimated_value_opportunity=total_value,
        total_estimated_volume_opportunity=total_volume,
        headline=headline,
        storytelling=story,
        top_actions=actions,
        top_retailers=retailers[:top_n],
        top_skus=skus[:top_n],
        top_regions=regions[:top_n],
        opportunities=actionable,
        one_slide=one_slide,
        risks=risks,
        limitations=limitations,
        methodology=METHODOLOGY,
    )
    if write_outputs:
        reports_dir = bundle.distribution_path.parent.parent / "brain_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"{bundle.stem}.brain.json"
        report.report_output_path = _display_path(out_path)
        out_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
        logger.info("brain_written path=%s actions=%s value=%s", out_path, len(actions), total_value)
    return report
