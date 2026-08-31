"""Assemble the Commercial Opportunity Pulse JSON from frozen agent outputs. No independent ranking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.reports.loader import ReportInputs, display_path, read_json

REPORT_VERSION = "V1"
TITLE = "UNILEVER SOUTH AFRICA"
DOCUMENT_NAME = "COMMERCIAL OPPORTUNITY PULSE"
TAGLINE = "Top 3 opportunities identified from current POS evidence"
OPPORTUNITY_LABEL = "Addressable opportunity estimate"
CAUSALITY_CLAIM = "none"

_SPECIALIST = {
    "DISTRIBUTION": "Distribution Agent V1",
    "PRICE": "Price Agent V1",
    "PROMOTION": "Promotion Agent V1",
    "MULTI-LEVER": "Commercial Brain V1 (primary lever retained)",
}


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def metric(value: Any, *, unit: str | None = None) -> dict[str, Any]:
    if value is None or value == "":
        return {"value": None, "available": False, "display": "Not available", "unit": unit}
    if isinstance(value, float) and value != value:
        return {"value": None, "available": False, "display": "Not available", "unit": unit}
    number = float(value) if isinstance(value, (int, float)) else value
    return {"value": number, "available": True, "display": number, "unit": unit}


def _match_opportunity(brain: dict[str, Any], action: dict[str, Any]) -> dict[str, Any] | None:
    for row in brain.get("opportunities") or []:
        if not isinstance(row, dict):
            continue
        if (
            row.get("product") == action.get("product")
            and row.get("retailer") == action.get("retailer")
            and row.get("region") == action.get("region")
        ):
            return row
    return None


def _story_action(story: dict[str, Any] | None, action: dict[str, Any]) -> dict[str, Any] | None:
    if not story:
        return None
    for row in story.get("actions") or []:
        if not isinstance(row, dict):
            continue
        if (
            row.get("product") == action.get("product")
            and row.get("retailer") == action.get("retailer")
            and row.get("region") == action.get("region")
        ):
            return row
    return None


def _price_promo_weeks(limitations: list[str], brain: dict[str, Any]) -> int | None:
    for note in limitations:
        if "overlapping price/promotion weeks" in note.lower():
            digits = "".join(ch if ch.isdigit() else " " for ch in note).split()
            if digits:
                return int(digits[0])
    coverage = str(brain.get("one_slide", {}).get("data_coverage") or "")
    if "price/promotion" in coverage.lower():
        digits = "".join(ch if ch.isdigit() else " " for ch in coverage.split("Price")[-1]).split()
        if digits:
            return int(digits[0])
    return None


def assemble(inputs: ReportInputs) -> dict[str, Any]:
    brain = inputs.brain
    actions = list(brain.get("top_actions") or [])
    if len(actions) < 3:
        raise ValueError("Commercial Brain did not emit three ranked actions.")
    top3 = actions[:3]
    story = inputs.storytelling or {}
    limitations = list(brain.get("limitations") or [])
    period = str(brain.get("current_period") or "")

    dist_meta = read_json(inputs.distribution_path) if inputs.distribution_path else None
    pos_weeks = (dist_meta or {}).get("periods_observed")
    period_list = [str(item) for item in ((dist_meta or {}).get("period_list") or [])]
    opportunities = [_opportunity(inputs, action, story, period) for action in top3]
    value_sum = sum(float(item["addressable_value"]) for item in opportunities)
    volume_sum = sum(float(item["addressable_volume"]) for item in opportunities)
    headline = story.get("headline") or (brain.get("storytelling") or {}).get("core_message") or brain.get("headline")
    supporting = story.get("subheadline") or (brain.get("storytelling") or {}).get("quantified_opportunity")
    implication = story.get("commercial_implication") or (brain.get("storytelling") or {}).get("next_step")
    macro = _macro(inputs, story)
    social = inputs.social
    report_limitations = _limitations(
        limitations,
        story,
        pos_weeks=pos_weeks,
        period=period,
        social=social,
        price_promo_weeks=_price_promo_weeks(limitations, brain),
    )
    return {
        "version": REPORT_VERSION,
        "title": TITLE,
        "document": DOCUMENT_NAME,
        "tagline": TAGLINE,
        "manufacturer": str(brain.get("manufacturer") or "Unilever"),
        "current_period": period,
        "generated_at": datetime.now(UTC).isoformat(),
        "causality_claim": CAUSALITY_CLAIM,
        "opportunity_label": OPPORTUNITY_LABEL,
        "story": {
            "headline": headline,
            "supporting_line": supporting,
            "commercial_implication": implication,
            "dominant_lever": story.get("dominant_lever") or brain.get("one_slide", {}).get("dominant_lever"),
            "key_insight": story.get("key_insight"),
            "source": "Storytelling Engine V1",
            "source_path": inputs.sources.get("storytelling"),
        },
        "top3_sum": {
            "addressable_value": value_sum,
            "addressable_volume": volume_sum,
            "label": OPPORTUNITY_LABEL,
            "disclaimer": (
                "Sum of the three Commercial Brain opportunities. "
                "This is an addressable opportunity estimate, not guaranteed incremental sales."
            ),
        },
        "opportunities": opportunities,
        "charts": _charts(opportunities),
        "macro": macro,
        "social": social,
        "quality": {
            "current_period": period,
            "pos_weeks": pos_weeks,
            "period_list": period_list,
            "price_promotion_weeks": _price_promo_weeks(limitations, brain),
            "brain_status": brain.get("status"),
            "sku_identity": "product name (ProductsID is not the canonical join key)",
            "data_coverage": story.get("data_coverage") or brain.get("one_slide", {}).get("data_coverage"),
        },
        "limitations": report_limitations,
        "methodology": story.get("methodology_note") or brain.get("methodology"),
        "sources": {
            **inputs.sources,
            "ranking": "Commercial Brain V1 top_actions (copied, not re-ranked)",
        },
        "provenance": {
            "ranking_agent": "Commercial Brain V1",
            "narrative_agent": "Storytelling Engine V1",
            "presentation_layer": "Opportunity PDF V1",
            "brain_path": inputs.sources.get("brain"),
            "period": period,
        },
    }


def _opportunity(inputs: ReportInputs, action: dict[str, Any], story: dict[str, Any], period: str) -> dict[str, Any]:
    grain = _match_opportunity(inputs.brain, action) or {}
    dist = inputs.distribution_index.get(
        (str(action.get("product") or ""), str(action.get("retailer") or ""), str(action.get("region") or "")),
        {},
    )
    story_row = _story_action(story, action) or {}
    lever = str(action.get("lever") or grain.get("dominant_lever") or "")
    store_gap = grain.get("distribution_gap")
    if store_gap is None:
        store_gap = dist.get("store_gap")
    if store_gap is None and story_row.get("store_gap") not in (None, 0, 0.0):
        store_gap = story_row.get("store_gap")
    current_stores = grain.get("distribution_stores")
    if current_stores is None:
        current_stores = dist.get("current_stores")
    return {
        "rank": action["rank"],
        "headline": action.get("headline"),
        "story_headline": story_row.get("headline"),
        "lever": lever,
        "product": action.get("product"),
        "brand": action.get("brand") or grain.get("brand"),
        "retailer": action.get("retailer"),
        "region": action.get("region"),
        "current_sales": metric(_first(action.get("current_sales"), grain.get("current_sales")), unit="R"),
        "addressable_value": float(action["addressable_value"]),
        "addressable_volume": float(action["addressable_volume"]),
        "confidence": action.get("confidence"),
        "store_gap": metric(store_gap, unit="stores"),
        "value_per_store": metric(_first(grain.get("sales_per_store"), dist.get("value_per_store")), unit="R"),
        "volume_per_store": metric(
            _first(grain.get("volume_per_store"), dist.get("volume_per_store")), unit="units"
        ),
        "current_stores": metric(current_stores, unit="stores"),
        "benchmark_stores": metric(dist.get("benchmark_stores"), unit="stores"),
        "why": action.get("why"),
        "recommended_action": action.get("recommended_action"),
        "evidence": list(action.get("evidence") or grain.get("evidence") or []),
        "double_counting_risk": grain.get("double_counting_risk") or _risk_from_evidence(action.get("evidence") or []),
        "limitations": list(grain.get("limitations") or []),
        "priority_score": action.get("priority_score"),
        "kind": "OPPORTUNITY",
        "provenance": {
            "agent": "Commercial Brain V1",
            "source": inputs.sources.get("brain"),
            "specialist_agent": _SPECIALIST.get(lever, "Commercial Brain V1"),
            "specialist_source": inputs.sources.get(
                {"DISTRIBUTION": "distribution", "PRICE": "price", "PROMOTION": "promotion"}.get(lever, "")
            ),
            "period": period,
            "observation_date": period,
            "opportunity_id": grain.get("opportunity_id"),
        },
    }


def _risk_from_evidence(evidence: list[Any]) -> str | None:
    for line in evidence:
        text = str(line)
        if "Double-counting risk:" in text:
            return text.split("Double-counting risk:", 1)[-1].strip().rstrip(".")
    return None


def _macro(inputs: ReportInputs, story: dict[str, Any]) -> dict[str, Any]:
    block = story.get("macro_context") if isinstance(story.get("macro_context"), dict) else None
    pack = block or inputs.macro
    if not pack:
        return {
            "included": False,
            "role": "absent",
            "label": "Supporting macro context",
            "status": "absent",
        }
    included = bool(pack.get("included", True))
    return {
        "included": included,
        "role": "supporting_context",
        "label": "Supporting macro context",
        "signal": pack.get("signal"),
        "evidence": pack.get("evidence"),
        "direction": pack.get("direction"),
        "confidence": pack.get("confidence"),
        "commercial_implication": pack.get("commercial_implication"),
        "sources": pack.get("sources") or [],
        "evidence_as_of": pack.get("evidence_as_of"),
        "source_path": pack.get("source_path") or (display_path(inputs.macro_path) if inputs.macro_path else None),
        "disclaimer": pack.get("causality_disclaimer")
        or "Macro context is supporting background only. It does not cause or recalculate POS opportunities.",
        "kind": "OBSERVATION",
    }


def _charts(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    ranking = [
        {
            "rank": item["rank"],
            "label": item["product"],
            "addressable_value": item["addressable_value"],
            "confidence": item["confidence"],
        }
        for item in opportunities
    ]
    coverage = []
    for item in opportunities:
        current = item["current_stores"]
        bench = item["benchmark_stores"]
        if current["available"] and bench["available"]:
            coverage.append(
                {
                    "rank": item["rank"],
                    "label": item["product"],
                    "current_stores": current["value"],
                    "benchmark_stores": bench["value"],
                }
            )
    sales_vs = []
    for item in opportunities:
        if item["current_sales"]["available"]:
            sales_vs.append(
                {
                    "rank": item["rank"],
                    "label": item["product"],
                    "current_sales": item["current_sales"]["value"],
                    "addressable_value": item["addressable_value"],
                }
            )
    return {
        "ranking": ranking,
        "coverage": coverage,
        "sales_versus_opportunity": sales_vs,
        "coverage_caption": (
            "Listed stores versus like-for-like benchmark. Gap-closing value is addressable, not booked sales."
        ),
        "sales_caption": "Current sales are distinct from addressable opportunity and are not incremental sales.",
        "ranking_caption": "Commercial Brain rank order. Values are addressable opportunity estimates.",
    }


def _limitations(
    brain_notes: list[str],
    story: dict[str, Any],
    *,
    pos_weeks: object,
    period: str,
    social: dict[str, Any],
    price_promo_weeks: int | None,
) -> list[str]:
    notes = [
        (
            "Opportunity PDF V1 is a presentation layer. "
            "It copies Commercial Brain ranking and does not rescore specialists."
        ),
        f"POS data period: {period or 'Not available'}.",
        f"POS weeks available: {pos_weeks if pos_weeks is not None else 'Not available'}.",
        f"Price/promotion weeks: {price_promo_weeks if price_promo_weeks is not None else 'Not available'}.",
        "Addressable opportunity estimates are directional and are not guaranteed incremental sales.",
        "No causal incrementality claim is made.",
        social.get("display") or "Social intelligence: not connected",
        "Macro context is supporting background only and does not change Commercial Brain ranking.",
    ]
    extra = list(story.get("limitations") or []) + list(brain_notes)
    seen = {item.casefold() for item in notes}
    for item in extra:
        text = str(item).strip()
        if text and text.casefold() not in seen:
            notes.append(text)
            seen.add(text.casefold())
    return notes
