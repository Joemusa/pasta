"""GDELT live-data smoke validation. Frozen specialist/SocialContextBrain logic is not changed."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.agents.consumer_needs.agent import run_consumer_needs
from backend.agents.consumer_sentiment.agent import run_consumer_sentiment
from backend.agents.social_brain.agent import (
    BRAIN_LIMITATIONS,
    _consumer_context,
    copy_pos_story,
    discover_brain_slide,
    overall_verdict,
    persist_brain,
    relate_signal,
    relate_theme,
)
from backend.agents.social_common.adapters import (
    LIVE,
    CollectionResult,
    PublicWebAdapter,
    RawPost,
    SourceAdapter,
    classify_source_class,
)
from backend.agents.social_common.alignment import parse_timestamp
from backend.agents.social_common.hashing import content_fingerprint
from backend.agents.social_common.language import assert_payload_safe
from backend.agents.social_common.models import (
    SCHEMA_DIR,
    SocialAgentStatus,
    SocialAlignment,
    SocialBrainReport,
    SourceRegistryEntry,
    load_social_config,
)
from backend.agents.social_common.paths import data_root_for, display_path, write_json
from backend.agents.social_common.queries import load_query_spec
from backend.agents.social_common.reports import quality_block
from backend.agents.social_listening.agent import run_social_listening
from backend.agents.social_trend.agent import run_social_trend

SMOKE_SPEC_PATH = SCHEMA_DIR / "social_gdelt_smoke.yaml"
WINDOW_DAYS = 90
SA_COUNTRIES = {"ZA", "SOUTH AFRICA"}


class ReplayAdapter(SourceAdapter):
    """Replays already-fetched LIVE posts. Does not invent records."""

    name = "public_web"
    source_type = "web"
    access_method = "gdelt_doc_2_0_api"

    def __init__(self, result: CollectionResult) -> None:
        self._result = result

    def collect(self) -> CollectionResult:
        posts = list(self._result.posts)
        entry = self._result.entry.model_copy(update={"record_count": len(posts)})
        return CollectionResult(entry=entry, posts=posts)


def _iso_z(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def drop_future_and_duplicates(
    posts: list[RawPost], *, now: datetime | None = None
) -> tuple[list[RawPost], dict[str, int]]:
    clock = now or datetime.now(UTC)
    window_start = clock - timedelta(days=WINDOW_DAYS)
    kept: list[RawPost] = []
    seen_url: set[str] = set()
    seen_text: set[str] = set()
    stats = {
        "raw": len(posts),
        "future": 0,
        "duplicate_url": 0,
        "duplicate_content": 0,
        "outside_window": 0,
        "kept": 0,
    }
    for item in posts:
        url_key = item.source_url.strip().casefold()
        if not url_key or url_key in seen_url:
            stats["duplicate_url"] += 1
            continue
        published = parse_timestamp(item.published_at)
        if published is not None:
            if published > clock:
                stats["future"] += 1
                continue
            if published < window_start:
                stats["outside_window"] += 1
                continue
        text_key = content_fingerprint("", item.text)
        if text_key in seen_text:
            stats["duplicate_content"] += 1
            continue
        seen_url.add(url_key)
        seen_text.add(text_key)
        kept.append(item)
    stats["kept"] = len(kept)
    return kept, stats


def collect_gdelt_live(spec_path: Path | None = None) -> CollectionResult:
    spec = load_query_spec(spec_path or SMOKE_SPEC_PATH)
    return PublicWebAdapter(spec=spec, env={"SOCIAL_LIVE_NETWORK": "1"}).collect()


def run_gdelt_validation(
    input_path: str | Path,
    *,
    spec_path: Path | None = None,
    write_outputs: bool = True,
    collected: CollectionResult | None = None,
) -> dict[str, Any]:
    root = data_root_for(Path(input_path))
    clock = datetime.now(UTC)
    observation_start = _iso_z(clock - timedelta(days=WINDOW_DAYS))
    observation_end = _iso_z(clock)
    collected_at = observation_end
    raw = collected if collected is not None else collect_gdelt_live(spec_path)
    retrieved = len(raw.posts)
    live_posts, stats = drop_future_and_duplicates(raw.posts, now=clock)
    live_posts = [item for item in live_posts if classify_source_class(item.data_quality) == LIVE]
    if any(classify_source_class(item.data_quality) == "FIXTURE" for item in raw.posts):
        raise RuntimeError("Fixture records were present in a live GDELT collection.")
    replay_entry = raw.entry.model_copy(update={"record_count": len(live_posts)})
    replay = CollectionResult(entry=replay_entry, posts=live_posts)
    reached = raw.entry.status in {"AVAILABLE", "PARTIAL"}
    connection = "SUCCESS" if reached and retrieved > 0 else "FAILED"
    summary: dict[str, Any] = {
        "title": "LIVE SOCIAL DATA VALIDATION",
        "source": "GDELT",
        "connection": connection,
        "live_data_status": "UNAVAILABLE",
        "observation_start": observation_start,
        "observation_end": observation_end,
        "collection_timestamp": collected_at,
        "records_retrieved": retrieved,
        "records_after_deduplication": len(live_posts),
        "records_successfully_normalised": 0,
        "records_successfully_analysed": 0,
        "dedupe_stats": stats,
        "registry": raw.entry.model_dump(mode="json"),
        "top_brands_detected": [],
        "top_categories_detected": [],
        "top_consumer_themes": [],
        "sentiment": None,
        "emerging_signals": [],
        "source_urls": [],
        "date_range": {"start": None, "end": None},
        "south_africa_specific_records": 0,
        "unknown_geography_records": 0,
        "other_geography_records": 0,
        "data_quality_issues": [],
    }
    if connection == "FAILED":
        summary["error"] = raw.entry.error
        summary["limitations"] = raw.entry.limitations
        summary["data_quality_issues"] = [
            "LIVE DATA STATUS = UNAVAILABLE. GDELT was not reached or returned no records. "
            "Fixtures were not substituted."
        ]
        if raw.entry.error:
            summary["data_quality_issues"].append(raw.entry.error)
        return _write_summary(root, summary, write_outputs)

    listening = run_social_listening(root, adapters=[ReplayAdapter(replay)], write_outputs=write_outputs)
    if any(classify_source_class(item.data_quality) != LIVE for item in listening.observations):
        raise RuntimeError("Non-LIVE observations were mixed into the GDELT live result.")
    sentiment = run_consumer_sentiment(root, listening=listening, write_outputs=write_outputs)
    needs = run_consumer_needs(root, listening=listening, write_outputs=write_outputs)
    trends = run_social_trend(root, listening=listening, write_outputs=write_outputs)
    brain = _brain_from_specialists(root, listening, sentiment, needs, trends, write_outputs=write_outputs)
    dates = sorted(item.published_at for item in listening.observations if item.published_at)
    za = [item for item in listening.observations if (item.country or "").upper() in SA_COUNTRIES]
    unknown_geo = [item for item in listening.observations if not item.country]
    other_geo = [
        item
        for item in listening.observations
        if item.country and (item.country or "").upper() not in SA_COUNTRIES
    ]
    issues = _quality_issues(listening.observations, raw, stats)
    summary.update(
        {
            "live_data_status": "LIVE — GDELT",
            "data_mode": listening.data_mode,
            "records_successfully_normalised": len(listening.observations),
            "records_successfully_analysed": sentiment.sentiment.evidence_count if sentiment.sentiment else 0,
            "top_brands_detected": _ranked(item.brand for item in listening.observations),
            "top_categories_detected": _ranked(item.category for item in listening.observations),
            "top_consumer_themes": [
                {"theme": item.theme, "frequency": item.frequency, "sentiment": item.sentiment}
                for item in needs.themes[:8]
            ],
            "sentiment": None if sentiment.sentiment is None else sentiment.sentiment.model_dump(mode="json"),
            "emerging_signals": [
                {"name": item.name, "status": item.status, "note": item.note} for item in trends.signals
            ],
            "source_urls": [item.source_url for item in listening.observations],
            "date_range": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
            "south_africa_specific_records": len(za),
            "unknown_geography_records": len(unknown_geo),
            "other_geography_records": len(other_geo),
            "data_quality_issues": issues,
            "social_context_brain_verdict": brain.verdict,
            "listening_path": listening.report_output_path,
            "brain_path": brain.report_output_path,
        }
    )
    if write_outputs:
        _snapshot_live_pack(root, listening, sentiment, needs, trends, brain)
    return _write_summary(root, summary, write_outputs)


def _ranked(values) -> list[str]:
    counts = Counter(value for value in values if value)
    return [name for name, _count in counts.most_common()]


def _quality_issues(observations, raw: CollectionResult, stats: dict[str, int]) -> list[str]:
    issues: list[str] = []
    missing_url = sum(1 for item in observations if not item.source_url)
    missing_date = sum(1 for item in observations if not item.published_at)
    missing_brand = sum(1 for item in observations if not item.brand)
    if missing_url:
        issues.append(f"{missing_url} observation(s) missing source_url")
    if missing_date:
        issues.append(f"{missing_date} observation(s) missing published_at (left null, not invented)")
    if missing_brand:
        issues.append(
            f"{missing_brand} observation(s) left brand/product/category unmatched "
            "because taxonomy evidence was insufficient"
        )
    if stats.get("future"):
        issues.append(f"{stats['future']} future-dated record(s) dropped")
    if stats.get("outside_window"):
        issues.append(
            f"{stats['outside_window']} record(s) older than the {WINDOW_DAYS}-day observation window dropped"
        )
    if stats.get("duplicate_url") or stats.get("duplicate_content"):
        issues.append(
            f"Deduplicated {stats.get('duplicate_url', 0)} URL duplicate(s) and "
            f"{stats.get('duplicate_content', 0)} content duplicate(s)"
        )
    if raw.entry.status == "PARTIAL":
        issues.append("GDELT collection was PARTIAL: " + (raw.entry.error or "some queries failed"))
    return issues


def _snapshot_live_pack(root: Path, listening, sentiment, needs, trends, brain) -> None:
    dest = root / "social_live_validation"
    write_json(dest / "social_listening_v1.json", listening.to_json_dict())
    write_json(dest / "consumer_sentiment_v1.json", sentiment.to_json_dict())
    write_json(dest / "consumer_needs_v1.json", needs.to_json_dict())
    write_json(dest / "social_trend_v1.json", trends.to_json_dict())
    write_json(dest / "social_context_brain_v1.json", brain.to_json_dict())


def _write_summary(root: Path, summary: dict[str, Any], write_outputs: bool) -> dict[str, Any]:
    report_text = render_validation_report(summary)
    summary["report_text"] = report_text
    if write_outputs:
        out = root / "social_live_validation" / "gdelt_smoke_summary.json"
        write_json(out, summary)
        (out.parent / "gdelt_smoke_report.txt").write_text(report_text + "\n", encoding="utf-8")
        summary["report_output_path"] = display_path(out)
    return summary


def render_validation_report(summary: dict[str, Any]) -> str:
    sentiment = summary.get("sentiment") or {}
    if isinstance(sentiment, dict) and sentiment:
        sentiment_line = (
            f"{sentiment.get('label')} (intensity {sentiment.get('intensity')}, "
            f"n={sentiment.get('evidence_count')})"
        )
    else:
        sentiment_line = "INSUFFICIENT_EVIDENCE"
    themes = summary.get("top_consumer_themes") or []
    if themes:
        theme_line = ", ".join(
            f"{item.get('theme')} ({item.get('frequency')}, {item.get('sentiment')})" for item in themes
        )
    else:
        theme_line = "none"
    signals = summary.get("emerging_signals") or []
    if signals:
        signal_line = "; ".join(f"{item.get('name')}={item.get('status')}" for item in signals)
    else:
        signal_line = "none"
    urls = summary.get("source_urls") or []
    url_block = "\n".join(f"- {url}" for url in urls) if urls else "- none"
    issues = summary.get("data_quality_issues") or []
    issue_block = "\n".join(f"- {item}" for item in issues) if issues else "- none"
    date_range = summary.get("date_range") or {}
    brands = summary.get("top_brands_detected") or []
    categories = summary.get("top_categories_detected") or []
    status = summary.get("live_data_status") or "UNAVAILABLE"
    status_line = f"LIVE DATA STATUS = {status}"
    return "\n".join(
        [
            "LIVE SOCIAL DATA VALIDATION",
            "",
            "Source: GDELT",
            "",
            f"Connection: {summary.get('connection')}",
            "",
            f"Records retrieved: {summary.get('records_retrieved')}",
            f"Records after deduplication: {summary.get('records_after_deduplication')}",
            f"Records successfully normalised: {summary.get('records_successfully_normalised')}",
            f"Records successfully analysed: {summary.get('records_successfully_analysed')}",
            "",
            f"Top brands detected: {', '.join(brands) if brands else 'none'}",
            f"Top categories detected: {', '.join(categories) if categories else 'none'}",
            f"Top consumer themes: {theme_line}",
            f"Sentiment: {sentiment_line}",
            f"Emerging signals: {signal_line}",
            "",
            "Source URLs:",
            url_block,
            "",
            f"Date range: {date_range.get('start')} to {date_range.get('end')}",
            f"observation_start: {summary.get('observation_start')}",
            f"observation_end: {summary.get('observation_end')}",
            f"collection_timestamp: {summary.get('collection_timestamp')}",
            "",
            f"South Africa-specific records: {summary.get('south_africa_specific_records')}",
            f"Unknown geography records: {summary.get('unknown_geography_records')}",
            "",
            "Data-quality issues:",
            issue_block,
            "",
            status_line,
        ]
    )


def _brain_from_specialists(root, listening, sentiment, needs, trends, *, write_outputs: bool) -> SocialBrainReport:
    """Apply frozen SocialContextBrain functions to already-analysed specialist payloads.

    ``run_social_brain`` always re-runs default live adapters. This helper uses the
    frozen brain functions without that extra fetch, so the live GDELT set is not
    mixed with Reddit/YouTube/NewsAPI attempts.
    """
    config = load_social_config()
    slide, brain_file = discover_brain_slide(root)
    pos = copy_pos_story(slide, brain_file)
    alignments: list[SocialAlignment] = [relate_theme(theme, pos.dominant_lever) for theme in needs.themes]
    alignments.extend(relate_signal(signal, pos.dominant_lever) for signal in trends.signals)
    if not alignments:
        alignments.append(
            SocialAlignment(
                finding="social_observations",
                relation="INSUFFICIENT_EVIDENCE",
                reason="No social observations were available to compare with Commercial Brain findings.",
                evidence_count=0,
            )
        )
    notes = [*BRAIN_LIMITATIONS, *list(config.limitations)]
    quality = quality_block(list(listening.observations), config, notes)
    report = SocialBrainReport(
        status=SocialAgentStatus.READY_WITH_WARNINGS,
        data_mode=listening.data_mode,
        verdict=overall_verdict(alignments),
        pos_story=pos,
        alignments=alignments,
        themes=list(needs.themes),
        signals=list(trends.signals),
        commercial_context=list(needs.commercial_context) + list(sentiment.commercial_context),
        source_registry=list(listening.source_registry),
        consumer_context=_consumer_context(sentiment, needs, trends),
        emerging_risks=[
            item.reason
            for item in alignments
            if item.relation in {"SUPPORTS", "ADD_CONTEXT"}
            and item.finding in {"availability", "availability_complaints"}
        ],
        emerging_opportunities=[
            item.reason
            for item in alignments
            if item.finding == "emerging_positive_themes" and item.relation == "ADD_CONTEXT"
        ],
        quality=quality,
        sources=sorted({*listening.sources, *needs.sources, *trends.sources}),
        limitations=notes,
    )
    assert_payload_safe(report.to_json_dict(), config)
    if write_outputs:
        persist_brain(report, root / "social_reports" / "social_context_brain_v1.json")
    return report


def unavailable_result(error: str) -> CollectionResult:
    return CollectionResult(
        entry=SourceRegistryEntry(
            source="public_web",
            source_type="web",
            access_method="gdelt_doc_2_0_api",
            status="UNAVAILABLE",
            record_count=0,
            error=error,
            limitations=["GDELT was not reached. Fixtures were not substituted."],
        ),
        posts=[],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GDELT live social data smoke validation")
    parser.add_argument("input", type=Path, help="Path to backend/data/")
    parser.add_argument("--spec", type=Path, default=SMOKE_SPEC_PATH)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    summary = run_gdelt_validation(args.input, spec_path=args.spec, write_outputs=not args.no_write)
    print(summary["report_text"])
    return 0 if summary.get("connection") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
