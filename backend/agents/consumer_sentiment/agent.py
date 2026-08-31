"""ConsumerSentimentAgent: classify conversation tone. Sentiment is not sales causality."""

from __future__ import annotations

from pathlib import Path

from backend.agents.social_common.alignment import non_future, split_recent_baseline
from backend.agents.social_common.language import assert_payload_safe
from backend.agents.social_common.models import (
    CommercialContext,
    SocialAgentStatus,
    SpecialistReport,
    load_social_config,
)
from backend.agents.social_common.paths import data_root_for
from backend.agents.social_common.pipeline import ensure_listening, report_dir
from backend.agents.social_common.reports import persist_report, quality_block
from backend.agents.social_common.sentiment import breakdown, classify_text, dimension_breakdowns
from backend.agents.social_common.taxonomy import load_taxonomy
from backend.agents.social_common.trends import classify_trend


def run_consumer_sentiment(
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
    observations = list(listening_report.observations)
    usable = non_future(observations)
    labels = [classify_text(item.text_or_excerpt, lexicon)[0] for item in usable]
    overall = breakdown(labels)
    recent, baseline = split_recent_baseline(usable, config)
    overall.trend = classify_trend(len(recent), len(baseline), config)
    by_dimension = dimension_breakdowns(usable, lexicon)
    for name, block in by_dimension.items():
        rows = [item for item in usable if _in_dimension(item, name)]
        rec, base = split_recent_baseline(rows, config)
        block.trend = classify_trend(len(rec), len(base), config)

    notes = list(config.limitations)
    notes.append("Sentiment is conversational tone, not sales causality.")
    notes.append("Future observations are excluded from POS-aligned sentiment.")
    if listening_report.data_mode != "LIVE":
        notes.insert(0, f"DATA MODE: {listening_report.data_mode}. Sentiment is not live social intelligence.")
    if not usable:
        notes.append("No usable observations — sentiment shares remain missing, not zero.")
    future_n = len(observations) - len(usable)
    if future_n:
        notes.append(f"{future_n} observation(s) excluded as FUTURE_LEAKAGE.")

    context = [
        CommercialContext(
            lever="NONE",
            channel="CONSUMER_SENTIMENT",
            statement=(
                "Consumer conversation sentiment is qualitative context for commercial findings. "
                "It is not proof of sales impact and does not create a commercial action."
            ),
            evidence_count=len(usable),
            relation_hint="ADD_CONTEXT" if usable else "INSUFFICIENT_EVIDENCE",
        )
    ]
    quality = quality_block(usable, config, notes)
    status = SocialAgentStatus.READY if usable else SocialAgentStatus.READY_WITH_WARNINGS
    report = SpecialistReport(
        agent="ConsumerSentimentAgent",
        status=status,
        data_mode=listening_report.data_mode,
        period=quality.date_range,
        observations=observations,
        commercial_context=context,
        sentiment=overall,
        sentiment_by_dimension=by_dimension,
        source_registry=list(listening_report.source_registry),
        confidence=quality.confidence,
        sources=sorted({item.source for item in usable}),
        limitations=notes,
        quality=quality,
    )
    assert_payload_safe(report.to_json_dict(), config)
    if write_outputs:
        persist_report(report, report_dir(root, report.data_mode) / "consumer_sentiment_v1.json")
    return report


def _in_dimension(item, name: str) -> bool:
    if name == "product":
        return bool(item.product)
    if name == "brand":
        return bool(item.brand)
    if name == "price":
        return "price" in item.topics
    if name == "promotion":
        return "promotion" in item.topics
    if name == "availability":
        return "availability" in item.topics
    if name == "service":
        return "retailer" in item.topics
    return False
