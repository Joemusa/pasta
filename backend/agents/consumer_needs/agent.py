"""ConsumerNeedsAgent: recurring needs supported by observations only."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from backend.agents.social_common.alignment import non_future
from backend.agents.social_common.confidence import insight_confidence
from backend.agents.social_common.language import assert_payload_safe
from backend.agents.social_common.models import (
    CommercialContext,
    SocialAgentStatus,
    SocialObservation,
    SpecialistReport,
    ThemeRecord,
    load_social_config,
)
from backend.agents.social_common.paths import data_root_for
from backend.agents.social_common.pipeline import ensure_listening, report_dir
from backend.agents.social_common.reports import persist_report, quality_block
from backend.agents.social_common.sentiment import classify_text, majority_sentiment
from backend.agents.social_common.taxonomy import load_taxonomy, match_needs, topic_spec


def run_consumer_needs(
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
    buckets: dict[str, list[SocialObservation]] = defaultdict(list)
    for obs in usable:
        for need in match_needs(obs.text_or_excerpt, taxonomy):
            buckets[need].append(obs)

    themes: list[ThemeRecord] = []
    for theme, rows in sorted(buckets.items(), key=lambda item: -len(item[1])):
        if len(rows) < config.theme_min_observations:
            continue
        labels = [classify_text(row.text_or_excerpt, lexicon)[0] for row in rows]
        spec = topic_spec(taxonomy, theme)
        levers = [str(item) for item in spec.get("commercial_levers") or []]
        channels = [str(item) for item in spec.get("channels") or []]
        implication = _implication(theme, len(rows))
        themes.append(
            ThemeRecord(
                theme=theme,
                frequency=len(rows),
                sentiment=majority_sentiment(labels),
                representative_evidence=[row.text_or_excerpt[:160] for row in rows[:3]],
                brands_affected=sorted({row.brand for row in rows if row.brand}),
                categories_affected=sorted({row.category for row in rows if row.category}),
                consumer_implication=implication,
                confidence=insight_confidence(rows, config),
                sources=sorted({row.source for row in rows}),
                commercial_levers=levers,
                channels=channels,
            )
        )

    context = [
        CommercialContext(
            lever=(theme.commercial_levers[0] if theme.commercial_levers else "NONE"),
            channel=(theme.channels[0] if theme.channels else "CONSUMER_NEEDS"),
            statement=theme.consumer_implication,
            evidence_count=theme.frequency,
            relation_hint="ADD_CONTEXT",
        )
        for theme in themes
    ]
    notes = list(config.limitations)
    notes.append("A need is listed only when supported by actual observations at the configured frequency threshold.")
    if not themes:
        notes.append("No recurring needs met the evidence threshold.")
    if listening_report.data_mode != "LIVE":
        notes.insert(0, f"DATA MODE: {listening_report.data_mode}. Needs are not live social intelligence.")
    quality = quality_block(usable, config, notes)
    status = SocialAgentStatus.READY if themes else SocialAgentStatus.READY_WITH_WARNINGS
    report = SpecialistReport(
        agent="ConsumerNeedsAgent",
        status=status,
        data_mode=listening_report.data_mode,
        period=quality.date_range,
        observations=[],
        themes=themes,
        commercial_context=context,
        source_registry=list(listening_report.source_registry),
        confidence=quality.confidence if themes else "LOW",
        sources=sorted({item.source for item in usable}),
        limitations=notes,
        quality=quality,
    )
    assert_payload_safe(report.to_json_dict(), config)
    if write_outputs:
        persist_report(report, report_dir(root, report.data_mode) / "consumer_needs_v1.json")
    return report


def _implication(theme: str, frequency: int) -> str:
    readable = theme.replace("_", " ")
    if theme == "availability":
        return (
            f"Consumer conversations contain recurring availability complaints "
            f"({frequency} observations). This is qualitative context, not a commercial action."
        )
    if theme in {"affordability", "value_for_money"}:
        return (
            f"Consumers discuss {readable} in public conversations "
            f"({frequency} observations). This adds context to value perception and is not a price action."
        )
    if theme == "promotions":
        return (
            f"Consumers discuss promotions in public conversations "
            f"({frequency} observations). This is not a promotion recommendation."
        )
    return (
        f"Consumers repeatedly discuss {readable} in public conversations "
        f"({frequency} observations). This is qualitative context, not a commercial action."
    )
