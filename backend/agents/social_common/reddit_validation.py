"""Reddit live-data smoke validation. Frozen specialist/SocialContextBrain logic is not changed."""

from __future__ import annotations

import argparse
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.agents.consumer_needs.agent import run_consumer_needs
from backend.agents.consumer_sentiment.agent import run_consumer_sentiment
from backend.agents.social_common.adapters import (
    LIVE,
    CollectionResult,
    RedditAdapter,
    classify_source_class,
)
from backend.agents.social_common.gdelt_validation import (
    SA_COUNTRIES,
    WINDOW_DAYS,
    ReplayAdapter,
    _brain_from_specialists,
    _iso_z,
    drop_future_and_duplicates,
)
from backend.agents.social_common.models import SCHEMA_DIR, SourceRegistryEntry, load_social_config
from backend.agents.social_common.paths import data_root_for, display_path, write_json
from backend.agents.social_common.queries import load_query_spec
from backend.agents.social_common.sentiment import classify_text
from backend.agents.social_common.taxonomy import load_taxonomy, match_needs
from backend.agents.social_listening.agent import run_social_listening
from backend.agents.social_trend.agent import run_social_trend

SMOKE_SPEC_PATH = SCHEMA_DIR / "social_reddit_smoke.yaml"


def subreddit_from_url(url: str) -> str | None:
    path = urlparse(url).path
    parts = [item for item in path.split("/") if item]
    if len(parts) >= 2 and parts[0].casefold() == "r":
        return parts[1]
    return None


def collect_reddit_live(spec_path: Path | None = None) -> CollectionResult:
    spec = load_query_spec(spec_path or SMOKE_SPEC_PATH)
    env = {**os.environ, "SOCIAL_LIVE_NETWORK": "1"}
    return RedditAdapter(spec=spec, env=env).collect()


def run_reddit_validation(
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
    raw = collected if collected is not None else collect_reddit_live(spec_path)
    retrieved = len(raw.posts)
    live_posts, stats = drop_future_and_duplicates(raw.posts, now=clock)
    live_posts = [item for item in live_posts if classify_source_class(item.data_quality) == LIVE]
    if any(classify_source_class(item.data_quality) == "FIXTURE" for item in raw.posts):
        raise RuntimeError("Fixture records were present in a live Reddit collection.")
    replay = CollectionResult(
        entry=raw.entry.model_copy(update={"record_count": len(live_posts)}),
        posts=live_posts,
    )
    reached = raw.entry.status in {"AVAILABLE", "PARTIAL"}
    connection = "SUCCESS" if reached and retrieved > 0 else "FAILED"
    summary: dict[str, Any] = {
        "title": "REDDIT LIVE SOCIAL DATA VALIDATION",
        "source": "Reddit",
        "connection": connection,
        "reddit_live_status": "UNAVAILABLE",
        "live_data_status": "UNAVAILABLE",
        "observation_start": observation_start,
        "observation_end": observation_end,
        "collection_timestamp": observation_end,
        "records_retrieved": retrieved,
        "records_after_deduplication": len(live_posts),
        "south_africa_specific_records": 0,
        "unknown_geography_records": 0,
        "records_by_brand": {},
        "records_by_category": {},
        "top_consumer_themes": [],
        "sentiment_distribution": {},
        "positive_themes": [],
        "negative_themes": [],
        "emerging_consumer_concerns": [],
        "emerging_consumer_opportunities": [],
        "source_subreddit_distribution": {},
        "date_range": {"start": None, "end": None},
        "data_quality_issues": [],
        "example_source_urls": [],
        "dedupe_stats": stats,
        "registry": raw.entry.model_dump(mode="json"),
        "observations": [],
        "causality_claim": "none",
        "limitations": [
            "Social sentiment is directional context only. It does not cause sales.",
            "Commercial Brain confidence is not upgraded because Reddit sentiment is present.",
        ],
    }
    if connection == "FAILED":
        summary["error"] = raw.entry.error
        summary["data_quality_issues"] = [
            "REDDIT LIVE STATUS = UNAVAILABLE. Credentials were missing, Reddit could not be "
            "reached, or no records were returned. Fixtures were not substituted."
        ]
        if raw.entry.error:
            summary["data_quality_issues"].append(raw.entry.error)
        return _write_summary(root, summary, write_outputs)

    listening = run_social_listening(root, adapters=[ReplayAdapter(replay)], write_outputs=write_outputs)
    if any(classify_source_class(item.data_quality) != LIVE for item in listening.observations):
        raise RuntimeError("Non-LIVE observations were mixed into the Reddit live result.")
    sentiment = run_consumer_sentiment(root, listening=listening, write_outputs=write_outputs)
    needs = run_consumer_needs(root, listening=listening, write_outputs=write_outputs)
    trends = run_social_trend(root, listening=listening, write_outputs=write_outputs)
    brain = _brain_from_specialists(root, listening, sentiment, needs, trends, write_outputs=write_outputs)
    taxonomy = load_taxonomy()
    lexicon = taxonomy.get("sentiment") or {}
    config = load_social_config()
    rows = _observation_rows(listening.observations, lexicon, taxonomy)
    if any(item.get("author") or item.get("author_handle") for item in rows):
        raise RuntimeError("Raw Reddit usernames were present in the validation payload.")
    dates = sorted(item.published_at for item in listening.observations if item.published_at)
    za = [item for item in listening.observations if (item.country or "").upper() in SA_COUNTRIES]
    unknown_geo = [item for item in listening.observations if not item.country]
    labels = [item["sentiment"] for item in rows]
    themes = [
        {"theme": item.theme, "frequency": item.frequency, "sentiment": item.sentiment}
        for item in needs.themes[:8]
    ]
    positive_themes = [item for item in themes if item["sentiment"] == "POSITIVE"]
    negative_themes = [item for item in themes if item["sentiment"] == "NEGATIVE"]
    concerns = [
        *list(brain.emerging_risks),
        *[f"{item['theme']} ({item['frequency']})" for item in negative_themes],
    ]
    opportunities = [
        *list(brain.emerging_opportunities),
        *[f"{item['theme']} ({item['frequency']})" for item in positive_themes],
    ]
    if not concerns:
        concerns = ["No emerging consumer concerns met the evidence threshold."]
    if not opportunities:
        opportunities = ["No emerging consumer opportunities met the evidence threshold."]
    subreddits = Counter(subreddit_from_url(item.source_url) or "unknown" for item in listening.observations)
    summary.update(
        {
            "reddit_live_status": "LIVE",
            "live_data_status": "LIVE — REDDIT",
            "data_mode": listening.data_mode,
            "records_successfully_normalised": len(listening.observations),
            "records_successfully_analysed": sentiment.sentiment.evidence_count if sentiment.sentiment else 0,
            "south_africa_specific_records": len(za),
            "unknown_geography_records": len(unknown_geo),
            "records_by_brand": dict(Counter((item.brand or "unmatched") for item in listening.observations)),
            "records_by_category": dict(
                Counter((item.category or "unmatched") for item in listening.observations)
            ),
            "top_consumer_themes": themes,
            "sentiment": None if sentiment.sentiment is None else sentiment.sentiment.model_dump(mode="json"),
            "sentiment_distribution": dict(Counter(labels)),
            "positive_themes": positive_themes,
            "negative_themes": negative_themes,
            "emerging_signals": [
                {"name": item.name, "status": item.status, "note": item.note} for item in trends.signals
            ],
            "emerging_consumer_concerns": concerns,
            "emerging_consumer_opportunities": opportunities,
            "source_subreddit_distribution": dict(subreddits.most_common()),
            "source_urls": [item.source_url for item in listening.observations],
            "example_source_urls": [item.source_url for item in listening.observations[:15]],
            "date_range": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
            "data_quality_issues": _quality_issues(listening.observations, raw, stats, rows),
            "social_context_brain_verdict": brain.verdict,
            "observations": rows,
            "excerpt_max_chars": config.excerpt_max_chars,
            "listening_path": listening.report_output_path,
            "brain_path": brain.report_output_path,
        }
    )
    if write_outputs:
        dest = root / "social_live_validation" / "reddit"
        write_json(dest / "social_listening_v1.json", listening.to_json_dict())
        write_json(dest / "consumer_sentiment_v1.json", sentiment.to_json_dict())
        write_json(dest / "consumer_needs_v1.json", needs.to_json_dict())
        write_json(dest / "social_trend_v1.json", trends.to_json_dict())
        write_json(dest / "social_context_brain_v1.json", brain.to_json_dict())
    return _write_summary(root, summary, write_outputs)


def _observation_rows(observations, lexicon: dict, taxonomy: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in observations:
        label, _intensity = classify_text(item.text_or_excerpt, lexicon)
        rows.append(
            {
                "source": item.source,
                "source_url": item.source_url,
                "published_at": item.published_at,
                "collected_at": item.collected_at,
                "data_quality": item.data_quality,
                "author_hash": item.author_id_hash,
                "brand": item.brand,
                "category": item.category,
                "product": item.product,
                "country": item.country,
                "region": item.region,
                "text_or_excerpt": item.text_or_excerpt,
                "sentiment": label,
                "themes": match_needs(item.text_or_excerpt, taxonomy) or list(item.topics),
                "subreddit": subreddit_from_url(item.source_url),
            }
        )
    return rows


def _quality_issues(
    observations, raw: CollectionResult, stats: dict[str, int], rows: list[dict[str, Any]]
) -> list[str]:
    issues: list[str] = []
    missing_url = sum(1 for item in observations if not item.source_url)
    missing_date = sum(1 for item in observations if not item.published_at)
    missing_hash = sum(1 for item in observations if not item.author_id_hash)
    missing_brand = sum(1 for item in observations if not item.brand)
    future_leak = sum(1 for item in observations if item.alignment_status == "FUTURE_LEAKAGE")
    if missing_url:
        issues.append(f"{missing_url} observation(s) missing source_url")
    if missing_date:
        issues.append(f"{missing_date} observation(s) missing published_at (left null, not invented)")
    if missing_hash:
        issues.append(
            f"{missing_hash} observation(s) have no author_hash because Reddit supplied no usable author"
        )
    if missing_brand:
        issues.append(
            f"{missing_brand} observation(s) left brand/product unmatched because taxonomy evidence was insufficient"
        )
    if future_leak:
        issues.append(
            f"{future_leak} observation(s) published after the POS period were retained as LIVE "
            "but excluded from sentiment analysis (FUTURE_LEAKAGE)"
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
        issues.append("Reddit collection was PARTIAL: " + (raw.entry.error or "some queries failed"))
    if any(not item.get("sentiment") for item in rows):
        issues.append("Some observations were missing directional sentiment labels")
    return issues


def _write_summary(root: Path, summary: dict[str, Any], write_outputs: bool) -> dict[str, Any]:
    report_text = render_reddit_report(summary)
    summary["report_text"] = report_text
    if write_outputs:
        dest = root / "social_live_validation"
        write_json(dest / "reddit_smoke_summary.json", summary)
        (dest / "reddit_smoke_report.txt").write_text(report_text + "\n", encoding="utf-8")
        summary["report_output_path"] = display_path(dest / "reddit_smoke_summary.json")
    return summary


def render_reddit_report(summary: dict[str, Any]) -> str:
    brands = summary.get("records_by_brand") or {}
    categories = summary.get("records_by_category") or {}
    themes = summary.get("top_consumer_themes") or []
    theme_line = (
        ", ".join(f"{item.get('theme')} ({item.get('frequency')}, {item.get('sentiment')})" for item in themes)
        if themes
        else "none"
    )
    dist = summary.get("sentiment_distribution") or {}
    sentiment_line = ", ".join(f"{key}={value}" for key, value in dist.items()) if dist else "none"
    pos = summary.get("positive_themes") or []
    neg = summary.get("negative_themes") or []
    subreddits = summary.get("source_subreddit_distribution") or {}
    urls = summary.get("example_source_urls") or []
    issues = summary.get("data_quality_issues") or []
    date_range = summary.get("date_range") or {}
    status = summary.get("reddit_live_status") or "UNAVAILABLE"
    return "\n".join(
        [
            "REDDIT LIVE SOCIAL DATA VALIDATION",
            "",
            f"REDDIT LIVE STATUS = {status}",
            "",
            f"1. Records retrieved: {summary.get('records_retrieved')}",
            f"2. Records after deduplication: {summary.get('records_after_deduplication')}",
            f"3. South Africa-specific records: {summary.get('south_africa_specific_records')}",
            f"4. Records by brand: {_fmt_counts(brands)}",
            f"5. Records by category: {_fmt_counts(categories)}",
            f"6. Top consumer themes: {theme_line}",
            f"7. Sentiment distribution: {sentiment_line}",
            f"8. Positive themes: {_fmt_theme_list(pos)}",
            f"9. Negative themes: {_fmt_theme_list(neg)}",
            "10. Emerging consumer concerns:",
            *_bullets(summary.get("emerging_consumer_concerns")),
            "11. Emerging consumer opportunities:",
            *_bullets(summary.get("emerging_consumer_opportunities")),
            f"12. Source/subreddit distribution: {_fmt_counts(subreddits)}",
            f"13. Date range: {date_range.get('start')} to {date_range.get('end')}",
            "14. Data-quality issues:",
            *_bullets(issues),
            "15. Example source URLs:",
            *_bullets(urls),
            "",
            "Social sentiment is directional only. It is not treated as a cause of sales.",
            "Commercial Brain confidence was not upgraded from Reddit sentiment.",
            f"observation_start: {summary.get('observation_start')}",
            f"observation_end: {summary.get('observation_end')}",
            f"collection_timestamp: {summary.get('collection_timestamp')}",
            f"Unknown geography records: {summary.get('unknown_geography_records')}",
        ]
    )


def _fmt_counts(values: dict[str, Any]) -> str:
    if not values:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in values.items())


def _fmt_theme_list(values: list[dict[str, Any]]) -> str:
    if not values:
        return "none"
    return ", ".join(f"{item.get('theme')} ({item.get('frequency')})" for item in values)


def _bullets(values) -> list[str]:
    items = [str(item) for item in (values or []) if item]
    if not items:
        return ["- none"]
    return [f"- {item}" for item in items]


def unavailable_reddit(error: str) -> CollectionResult:
    return CollectionResult(
        entry=SourceRegistryEntry(
            source="reddit",
            source_type="social",
            access_method="official_oauth_api",
            status="UNAVAILABLE",
            record_count=0,
            error=error,
            limitations=["Reddit was not reached. Fixtures were not substituted."],
        ),
        posts=[],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reddit live social data smoke validation")
    parser.add_argument("input", type=Path, help="Path to backend/data/")
    parser.add_argument("--spec", type=Path, default=SMOKE_SPEC_PATH)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    summary = run_reddit_validation(args.input, spec_path=args.spec, write_outputs=not args.no_write)
    print(summary["report_text"])
    return 0 if summary.get("connection") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
