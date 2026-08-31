"""SocialContextBrain: compare social intelligence with Commercial Brain findings. Read-only POS copy."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.agents.consumer_needs.agent import run_consumer_needs
from backend.agents.consumer_sentiment.agent import run_consumer_sentiment
from backend.agents.social_common.language import assert_payload_safe
from backend.agents.social_common.models import (
    BrainRelation,
    PosStoryCopy,
    SocialAgentStatus,
    SocialAlignment,
    SocialBrainReport,
    ThemeRecord,
    TrendRecord,
    load_social_config,
)
from backend.agents.social_common.paths import SocialLoadError, data_root_for, display_path, read_json
from backend.agents.social_common.pipeline import report_dir
from backend.agents.social_common.reports import quality_block
from backend.agents.social_listening.agent import run_social_listening
from backend.agents.social_trend.agent import run_social_trend

logger = logging.getLogger("backend.agents.social_brain")

BRAIN_LIMITATIONS = [
    "SocialContextBrain is an external consumer-context layer. It does not modify frozen POS or macro agents.",
    "It does not recalculate POS sales, distribution gaps, price opportunities, promotion opportunities, "
    "addressable value, addressable volume, or specialist confidence.",
    "Social intelligence does not create a commercial action.",
    "Sentiment is not treated as sales causality.",
    "Future social observations are not used to explain historical POS periods.",
]


def _extract_one_slide(payload: dict) -> dict:
    if isinstance(payload.get("one_slide"), dict):
        return payload["one_slide"]
    if isinstance(payload.get("top_actions"), list):
        return payload
    raise SocialLoadError("JSON is not a Commercial Brain one-slide or *.brain.json report")


def discover_brain_slide(path: Path) -> tuple[dict, Path]:
    path = path.expanduser().resolve()
    if path.is_file():
        return _extract_one_slide(read_json(path, kind="Commercial Brain slide")), path
    named = [
        path / "commercial_brain_v1_one_slide.json",
        path / "brain_reports" / "commercial_brain_v1_one_slide.json",
    ]
    candidates = [item for item in named if item.is_file()]
    brain_dir = path / "brain_reports"
    if brain_dir.is_dir():
        candidates.extend(sorted(brain_dir.glob("*.brain.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    if not candidates:
        raise SocialLoadError(f"No Commercial Brain JSON under {path}")
    chosen = candidates[0]
    return _extract_one_slide(read_json(chosen, kind="Commercial Brain slide")), chosen


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def copy_pos_story(slide: dict, source: Path) -> PosStoryCopy:
    actions = slide.get("top_actions") or []
    brands = sorted(
        {str(item.get("brand")) for item in actions if isinstance(item, dict) and item.get("brand")}
    )
    products = sorted(
        {str(item.get("product")) for item in actions if isinstance(item, dict) and item.get("product")}
    )
    return PosStoryCopy(
        headline=None if slide.get("headline") is None else str(slide.get("headline")),
        dominant_lever=_dominant_lever(slide, actions),
        total_addressable_value_opportunity=_num(
            slide.get("total_addressable_value_opportunity", slide.get("total_estimated_value_opportunity"))
        ),
        total_addressable_volume_opportunity=_num(
            slide.get("total_addressable_volume_opportunity", slide.get("total_estimated_volume_opportunity"))
        ),
        n_actions=len(actions) if isinstance(actions, list) else None,
        action_brands=brands,
        action_products=products,
        source_brain_slide=display_path(source),
    )


def _dominant_lever(slide: dict, actions: object) -> str | None:
    if slide.get("dominant_lever"):
        return str(slide["dominant_lever"])
    if not isinstance(actions, list) or not actions:
        return None
    levers = [str(item.get("lever") or "") for item in actions if isinstance(item, dict)]
    if not levers:
        return None
    return max(set(levers), key=levers.count)


def relate_theme(theme: ThemeRecord, dominant_lever: str | None) -> SocialAlignment:
    lever = (dominant_lever or "").upper()
    levers = {item.upper() for item in theme.commercial_levers}
    channels = {item.upper() for item in theme.channels}
    if theme.theme == "availability" or "AVAILABILITY" in channels:
        if theme.sentiment == "POSITIVE" and lever == "DISTRIBUTION":
            return SocialAlignment(
                finding=theme.theme,
                relation="CONTRADICTS",
                reason=(
                    "Consumers describe the brand as easy to find, which does not match a distribution-gap story. "
                    "This does not change POS coverage values."
                ),
                evidence_count=theme.frequency,
                commercial_levers=["DISTRIBUTION"],
            )
        if lever == "DISTRIBUTION" or "DISTRIBUTION" in levers:
            return SocialAlignment(
                finding=theme.theme,
                relation="SUPPORTS",
                reason=(
                    "Consumer conversations contain recurring availability complaints. "
                    "This supports a distribution finding as qualitative context. "
                    "It is not a commercial action and does not change POS gap values."
                ),
                evidence_count=theme.frequency,
                commercial_levers=["DISTRIBUTION"],
            )
        return SocialAlignment(
            finding=theme.theme,
            relation="ADD_CONTEXT",
            reason="Availability talk is consumer context and is not used to invent a distribution action.",
            evidence_count=theme.frequency,
            commercial_levers=list(theme.commercial_levers),
        )
    if theme.theme in {"affordability", "value_for_money"} or "PRICE" in levers:
        return SocialAlignment(
            finding=theme.theme,
            relation="ADD_CONTEXT",
            reason=(
                "Consumers discuss price or value in conversation. "
                "This adds context to a price finding and is not proof of a price opportunity."
            ),
            evidence_count=theme.frequency,
            commercial_levers=["PRICE"],
        )
    if theme.theme == "promotions" or "PROMOTION" in levers:
        return SocialAlignment(
            finding=theme.theme,
            relation="ADD_CONTEXT",
            reason="Promotion talk is consumer context and is not a promotion recommendation.",
            evidence_count=theme.frequency,
            commercial_levers=["PROMOTION"],
        )
    if "COMPETITOR_PRESSURE" in channels:
        return SocialAlignment(
            finding=theme.theme,
            relation="ADD_CONTEXT",
            reason="Competitor mentions are qualitative pressure context, not a competitive action.",
            evidence_count=theme.frequency,
            commercial_levers=list(theme.commercial_levers),
        )
    return SocialAlignment(
        finding=theme.theme,
        relation="ADD_CONTEXT",
        reason="Theme is consumer context and is not used to rescore Commercial Brain rankings.",
        evidence_count=theme.frequency,
        commercial_levers=list(theme.commercial_levers),
    )


def relate_signal(signal: TrendRecord, dominant_lever: str | None) -> SocialAlignment:
    if signal.status == "INSUFFICIENT_EVIDENCE":
        return SocialAlignment(
            finding=signal.name,
            relation="INSUFFICIENT_EVIDENCE",
            reason=signal.note,
            evidence_count=signal.evidence_count,
        )
    if signal.name == "availability_complaints" and (dominant_lever or "").upper() == "DISTRIBUTION":
        return SocialAlignment(
            finding=signal.name,
            relation="SUPPORTS",
            reason=(
                "Availability complaints in consumer conversation support a distribution finding as context. "
                "POS coverage gaps remain the source of the commercial ranking."
            ),
            evidence_count=signal.evidence_count,
            commercial_levers=["DISTRIBUTION"],
        )
    if signal.name in {"price_value", "promotion_discussions", "competitor_mentions"}:
        return SocialAlignment(
            finding=signal.name,
            relation="ADD_CONTEXT",
            reason=signal.note,
            evidence_count=signal.evidence_count,
        )
    return SocialAlignment(
        finding=signal.name,
        relation="NEUTRAL" if signal.status == "STABLE" else "ADD_CONTEXT",
        reason=signal.note,
        evidence_count=signal.evidence_count,
    )


def overall_verdict(alignments: list[SocialAlignment]) -> BrainRelation:
    usable = [item for item in alignments if item.relation != "INSUFFICIENT_EVIDENCE"]
    if not usable:
        return "INSUFFICIENT_EVIDENCE"
    counts = {label: 0 for label in ("SUPPORTS", "CONTRADICTS", "ADD_CONTEXT", "NEUTRAL")}
    for item in usable:
        counts[item.relation] = counts.get(item.relation, 0) + 1
    if counts["CONTRADICTS"] > counts["SUPPORTS"]:
        return "CONTRADICTS"
    if counts["SUPPORTS"] > 0:
        return "SUPPORTS"
    if counts["ADD_CONTEXT"] > 0:
        return "ADD_CONTEXT"
    return "NEUTRAL"


def run_social_brain(
    input_path: str | Path,
    *,
    fixture_path: str | Path | None = None,
    config_path: str | Path | None = None,
    write_outputs: bool = True,
) -> SocialBrainReport:
    source = Path(input_path).expanduser().resolve()
    root = data_root_for(source)
    config = load_social_config(None if config_path is None else Path(config_path))
    slide, brain_file = discover_brain_slide(source if source.is_dir() else root)
    pos = copy_pos_story(slide, brain_file)
    listening = run_social_listening(
        root, fixture_path=fixture_path, write_outputs=write_outputs
    )
    sentiment = run_consumer_sentiment(
        root, listening=listening, write_outputs=write_outputs, config_path=config_path
    )
    needs = run_consumer_needs(
        root, listening=listening, write_outputs=write_outputs, config_path=config_path
    )
    trends = run_social_trend(
        root, listening=listening, write_outputs=write_outputs, config_path=config_path
    )
    alignments: list[SocialAlignment] = []
    for theme in needs.themes:
        alignments.append(relate_theme(theme, pos.dominant_lever))
    for signal in trends.signals:
        alignments.append(relate_signal(signal, pos.dominant_lever))
    if not alignments:
        alignments.append(
            SocialAlignment(
                finding="social_observations",
                relation="INSUFFICIENT_EVIDENCE",
                reason="No social observations were available to compare with Commercial Brain findings.",
                evidence_count=0,
            )
        )
    verdict = overall_verdict(alignments)
    consumer_context = _consumer_context(sentiment, needs, trends)
    risks = [
        item.reason
        for item in alignments
        if item.relation in {"SUPPORTS", "ADD_CONTEXT"} and item.finding in {"availability", "availability_complaints"}
    ]
    opportunities = [
        item.reason
        for item in alignments
        if item.finding in {"emerging_positive_themes"} and item.relation == "ADD_CONTEXT"
    ]
    notes = [*BRAIN_LIMITATIONS, *list(config.limitations)]
    if listening.data_mode != "LIVE":
        notes.insert(0, f"DATA MODE: {listening.data_mode}. SocialContextBrain is not using live social data.")
    quality = quality_block(list(listening.observations), config, notes)
    context = list(needs.commercial_context) + list(sentiment.commercial_context)
    report = SocialBrainReport(
        status=SocialAgentStatus.READY_WITH_WARNINGS,
        data_mode=listening.data_mode,
        verdict=verdict,
        pos_story=pos,
        alignments=alignments,
        themes=list(needs.themes),
        signals=list(trends.signals),
        commercial_context=context,
        source_registry=list(listening.source_registry),
        consumer_context=consumer_context,
        emerging_risks=risks,
        emerging_opportunities=opportunities,
        quality=quality,
        sources=sorted({*listening.sources, *needs.sources, *trends.sources}),
        limitations=notes,
    )
    assert_payload_safe(report.to_json_dict(), config)
    if write_outputs:
        persist_brain(report, report_dir(root, report.data_mode) / "social_context_brain_v1.json")
        logger.info("social_brain_written path=%s verdict=%s", report.report_output_path, verdict)
    return report


def persist_brain(report: SocialBrainReport, out_path: Path) -> SocialBrainReport:
    from backend.agents.social_common.paths import write_json

    report.report_output_path = display_path(out_path)
    write_json(out_path, report.to_json_dict())
    return report


def _consumer_context(sentiment, needs, trends) -> list[str]:
    lines: list[str] = []
    if sentiment.sentiment is not None:
        lines.append(
            f"Overall consumer conversation sentiment: {sentiment.sentiment.label} "
            f"(intensity {sentiment.sentiment.intensity}, n={sentiment.sentiment.evidence_count}). "
            "This is not sales causality."
        )
        if sentiment.sentiment.share_positive is None and sentiment.sentiment.evidence_count == 0:
            lines.append("Sentiment shares remain missing because no observations were available.")
    for theme in needs.themes[:5]:
        lines.append(theme.consumer_implication)
    for signal in trends.signals:
        if signal.status not in {"INSUFFICIENT_EVIDENCE", "STABLE"}:
            lines.append(signal.note)
    if not lines:
        lines.append("No consumer context is available from social sources.")
    return lines
