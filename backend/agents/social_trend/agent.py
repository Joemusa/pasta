"""SocialTrendAgent: emerging conversation changes. Insufficient history is not a trend."""

from __future__ import annotations

from pathlib import Path

from backend.agents.social_common.alignment import non_future, split_recent_baseline
from backend.agents.social_common.confidence import insight_confidence
from backend.agents.social_common.language import assert_payload_safe
from backend.agents.social_common.models import (
    CommercialContext,
    SocialAgentStatus,
    SpecialistReport,
    TrendRecord,
    load_social_config,
)
from backend.agents.social_common.paths import data_root_for
from backend.agents.social_common.pipeline import ensure_listening, report_dir
from backend.agents.social_common.reports import persist_report, quality_block
from backend.agents.social_common.sentiment import classify_text
from backend.agents.social_common.taxonomy import load_taxonomy
from backend.agents.social_common.trends import classify_trend

TRACKED = (
    ("conversation_volume", "overall conversation volume", lambda _item, _lex: True),
    ("availability_complaints", "availability complaints", lambda item, _lex: "availability" in item.topics),
    ("price_value", "price/value concerns", lambda item, _lex: "price" in item.topics),
    ("promotion_discussions", "promotion discussions", lambda item, _lex: "promotion" in item.topics),
    ("competitor_mentions", "competitor mentions", lambda item, _lex: item.competitor is not None),
    ("new_product_discussions", "named product discussions", lambda item, _lex: item.product is not None),
    (
        "emerging_complaints",
        "negative conversation",
        lambda item, lex: classify_text(item.text_or_excerpt, lex)[0] == "NEGATIVE",
    ),
    (
        "emerging_positive_themes",
        "positive conversation",
        lambda item, lex: classify_text(item.text_or_excerpt, lex)[0] == "POSITIVE",
    ),
)


def run_social_trend(
    input_path: str | Path,
    *,
    listening: SpecialistReport | None = None,
    fixture_path: str | Path | None = None,
    config_path: str | Path | None = None,
    taxonomy_path: str | Path | None = None,
    write_outputs: bool = True,
) -> SpecialistReport:
    source = Path(input_path).expanduser().resolve()
    root = data_root_for(source)
    config = load_social_config(None if config_path is None else Path(config_path))
    taxonomy = load_taxonomy(None if taxonomy_path is None else Path(taxonomy_path))
    lexicon = taxonomy.get("sentiment") or {}
    listening_report = ensure_listening(
        root, listening=listening, fixture_path=fixture_path, write_outputs=write_outputs
    )
    usable = non_future(list(listening_report.observations))
    signals: list[TrendRecord] = []
    for name, label, predicate in TRACKED:
        rows = [item for item in usable if predicate(item, lexicon)]
        recent, baseline = split_recent_baseline(rows, config)
        status = classify_trend(len(recent), len(baseline), config)
        note = _note(label, status, len(recent), len(baseline))
        signals.append(
            TrendRecord(
                name=name,
                status=status,
                recent_count=len(recent),
                baseline_count=len(baseline),
                evidence_count=len(rows),
                source_count=len({item.source for item in rows}),
                note=note,
                confidence=insight_confidence(rows, config) if status != "INSUFFICIENT_EVIDENCE" else "LOW",
            )
        )

    context = [
        CommercialContext(
            lever="NONE",
            channel="CONSUMER_NEEDS",
            statement=item.note,
            evidence_count=item.evidence_count,
            relation_hint=(
                "INSUFFICIENT_EVIDENCE"
                if item.status == "INSUFFICIENT_EVIDENCE"
                else "NEUTRAL"
                if item.status == "STABLE"
                else "ADD_CONTEXT"
            ),
        )
        for item in signals
        if item.status != "STABLE"
    ]
    notes = list(config.limitations)
    notes.append("A trend is not claimed when recent volume or historical baseline is below the configured threshold.")
    if listening_report.data_mode != "LIVE":
        notes.insert(0, f"DATA MODE: {listening_report.data_mode}. Trends are not live social intelligence.")
    quality = quality_block(usable, config, notes)
    ready = any(item.status != "INSUFFICIENT_EVIDENCE" for item in signals)
    report = SpecialistReport(
        agent="SocialTrendAgent",
        status=SocialAgentStatus.READY if ready else SocialAgentStatus.READY_WITH_WARNINGS,
        data_mode=listening_report.data_mode,
        period=quality.date_range,
        observations=[],
        signals=signals,
        commercial_context=context,
        source_registry=list(listening_report.source_registry),
        confidence=quality.confidence if ready else "LOW",
        sources=sorted({item.source for item in usable}),
        limitations=notes,
        quality=quality,
    )
    assert_payload_safe(report.to_json_dict(), config)
    if write_outputs:
        persist_report(report, report_dir(root, report.data_mode) / "social_trend_v1.json")
    return report


def _note(label: str, status: str, recent: int, baseline: int) -> str:
    if status == "INSUFFICIENT_EVIDENCE":
        return (
            f"Insufficient history to call {label} a trend "
            f"(recent={recent}, baseline={baseline})."
        )
    return (
        f"Conversation pattern for {label} is {status} "
        f"(recent={recent}, baseline={baseline}). This is not a commercial action."
    )
