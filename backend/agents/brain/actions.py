"""Top 3 actions and Storytelling with Data narrative. Never claim guaranteed sales."""

from __future__ import annotations

from collections import Counter

from backend.agents.brain.models import (
    BrainAction,
    BrainConfig,
    BrainOpportunity,
    DominantLever,
    OneSlide,
    Storytelling,
)


def _short_product(name: str) -> str:
    return name if len(name) <= 48 else name[:45] + "..."


def action_headline(opp: BrainOpportunity) -> str:
    sku = _short_product(opp.product)
    if opp.dominant_lever == DominantLever.DISTRIBUTION.value:
        return f"Expand distribution of {sku} in {opp.region}"
    if opp.dominant_lever == DominantLever.PROMOTION.value:
        return f"Target promotion of {sku} at {opp.retailer} in {opp.region}"
    if opp.dominant_lever == DominantLever.PRICE.value:
        return f"Test price position of {sku} at {opp.retailer} in {opp.region}"
    if opp.dominant_lever == DominantLever.MULTI_LEVER.value:
        return f"Expand distribution of {sku} in {opp.region} and support with targeted promotion"
    return f"Review {sku} at {opp.retailer} in {opp.region}"


def action_why(opp: BrainOpportunity) -> str:
    conf_note = (
        "The signal is directional and is not guaranteed incremental sales."
        if opp.confidence != "HIGH"
        else "Evidence is stronger than the rest of this short panel, but sales are still not guaranteed."
    )
    if opp.dominant_lever == DominantLever.DISTRIBUTION.value:
        gap = f"{opp.distribution_gap:.0f} stores" if opp.distribution_gap is not None else "a material store gap"
        return (
            f"Listed-store economics are attractive while coverage sits {gap} below the like-for-like benchmark "
            f"at {opp.retailer} in {opp.region}. Price or promotion is not the first lever: low coverage is "
            f"limiting reach. {conf_note}"
        )
    if opp.dominant_lever == DominantLever.PROMOTION.value:
        return (
            f"Distribution is adequate and directional promo response at {opp.retailer} in {opp.region} is stronger "
            f"than a price intervention on this grain. {conf_note}"
        )
    if opp.dominant_lever == DominantLever.PRICE.value:
        return (
            f"Coverage is adequate and promotion does not explain the gap, while realised price is materially "
            f"different from the like-for-like benchmark at {opp.retailer} in {opp.region}. {conf_note}"
        )
    if opp.dominant_lever == DominantLever.MULTI_LEVER.value:
        return (
            f"Store coverage is the primary constraint, and listed-store promo response is complementary rather than "
            f"a restatement of the same gap. The value kept is the distribution opportunity only. {conf_note}"
        )
    return f"Evidence is too weak for a commercial action. {conf_note}"


def select_top_actions(opportunities: list[BrainOpportunity], config: BrainConfig) -> list[BrainAction]:
    ranked = sorted(
        [
            item
            for item in opportunities
            if item.dominant_lever != DominantLever.INSUFFICIENT_EVIDENCE.value
            and item.opportunity_value >= config.min_primary_value
            and item.opportunity_volume >= config.min_action_volume
        ],
        key=lambda item: (-item.priority_score, -item.opportunity_value, item.product),
    )
    picked: list[BrainOpportunity] = []
    product_counts: Counter[str] = Counter()
    lever_counts: Counter[str] = Counter()
    seen: set[str] = set()

    def try_pick(pool: list[BrainOpportunity], *, relax: bool) -> None:
        for item in pool:
            if len(picked) >= config.n_actions:
                return
            if item.opportunity_id in seen:
                continue
            if item.region in config.excluded_action_regions:
                continue
            if not relax:
                if product_counts[item.product] >= config.max_actions_per_product:
                    continue
                if lever_counts[item.dominant_lever] >= config.max_actions_per_lever:
                    continue
            picked.append(item)
            seen.add(item.opportunity_id)
            product_counts[item.product] += 1
            lever_counts[item.dominant_lever] += 1

    try_pick(ranked, relax=False)
    try_pick(ranked, relax=True)
    actions: list[BrainAction] = []
    for index, opp in enumerate(picked[: config.n_actions], start=1):
        actions.append(
            BrainAction(
                rank=index,
                action_number=index,
                lever=opp.dominant_lever,
                headline=action_headline(opp),
                why=action_why(opp),
                product=opp.product,
                brand=opp.brand,
                retailer=opp.retailer,
                region=opp.region,
                estimated_value=opp.opportunity_value,
                estimated_volume=opp.opportunity_volume,
                confidence=opp.confidence,
                recommended_action=opp.recommended_action,
                evidence=opp.evidence,
                priority_score=opp.priority_score,
            )
        )
    return actions


def core_headline(opportunities: list[BrainOpportunity], actions: list[BrainAction], top_region: str | None) -> str:
    value_by_lever: dict[str, float] = {}
    for item in opportunities:
        value_by_lever[item.dominant_lever] = value_by_lever.get(item.dominant_lever, 0.0) + item.opportunity_value
    region = top_region or (actions[0].region if actions else "priority markets")
    if not value_by_lever:
        return f"Unilever does not yet have a validated near-term growth lever in {region}"
    top_lever = max(value_by_lever.items(), key=lambda item: (item[1], item[0]))[0]
    if top_lever == DominantLever.DISTRIBUTION.value:
        return f"Distribution is the largest near-term growth lever in {region}"
    if top_lever == DominantLever.PROMOTION.value:
        retailer = actions[0].retailer if actions else "priority retailers"
        return f"Promotion is the near-term growth lever to test at {retailer}"
    if top_lever == DominantLever.PRICE.value:
        return f"Like-for-like price tests, not blanket discounting, are the next lever in {region}"
    if top_lever == DominantLever.MULTI_LEVER.value:
        return f"Coverage plus targeted promotion is the near-term growth combination in {region}"
    return f"Unilever's near-term growth depends on a small set of actions in {region}"


def build_story(
    *,
    headline: str,
    actions: list[BrainAction],
    total_value: float,
    total_volume: float,
) -> Storytelling:
    supporting = [item.headline for item in actions]
    quantified = (
        f"After removing double-counted specialist overlap, the primary commercial opportunity is "
        f"R{total_value:,.0f} and {total_volume:,.0f} units. These figures are estimated, not guaranteed sales."
    )
    if actions:
        first = actions[0]
        next_step = (
            f"Start with Action 1: {first.recommended_action} Treat the result as a test, not booked revenue."
        )
    else:
        next_step = "Do not brief a commercial test until specialist evidence meets the action bar."
    return Storytelling(
        core_message=headline,
        supporting_actions=supporting,
        quantified_opportunity=quantified,
        next_step=next_step,
    )


def headline_support(story: Storytelling, actions: list[BrainAction]) -> str:
    if len(actions) >= 3:
        scored = (
            "The three actions below are scored for size, evidence, actionability, "
            "and data quality — not by adding distribution, price, and promotion together."
        )
        message = story.core_message.rstrip(".")
        return f"{message}. {scored} {story.quantified_opportunity}"
    return story.quantified_opportunity


def build_one_slide(
    *,
    headline: str,
    support: str,
    total_value: float,
    total_volume: float,
    actions: list[BrainAction],
    retailers: list[dict[str, object]],
    skus: list[dict[str, object]],
    regions: list[dict[str, object]],
    risks: list[str],
    limitations: list[str],
    methodology: str,
    data_coverage: str,
) -> OneSlide:
    return OneSlide(
        report_title="Unilever Commercial Brain V1",
        headline=headline,
        headline_support=support,
        total_estimated_value_opportunity=total_value,
        total_estimated_volume_opportunity=total_volume,
        top_actions=[
            {
                "rank": item.rank,
                "lever": item.lever,
                "headline": item.headline,
                "product": item.product,
                "brand": item.brand,
                "retailer": item.retailer,
                "region": item.region,
                "estimated_value": item.estimated_value,
                "estimated_volume": item.estimated_volume,
                "confidence": item.confidence,
                "why": item.why,
                "recommended_action": item.recommended_action,
                "evidence": item.evidence,
            }
            for item in actions
        ],
        retailer_priorities=retailers,
        sku_priorities=skus,
        region_priorities=regions,
        risks=risks,
        limitations=limitations,
        methodology=methodology,
        data_coverage=data_coverage,
    )
