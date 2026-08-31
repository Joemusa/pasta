"""SocialListeningAgent: collect and normalise public conversations. Posts are never invented."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.agents.social_common.adapters import FixtureAdapter, RawPost, SourceAdapter, default_live_adapters
from backend.agents.social_common.alignment import align_published
from backend.agents.social_common.hashing import content_fingerprint, hash_author
from backend.agents.social_common.language import assert_no_causal_language
from backend.agents.social_common.models import (
    DataMode,
    SocialAgentStatus,
    SocialConfig,
    SocialObservation,
    SpecialistReport,
    load_social_config,
)
from backend.agents.social_common.paths import data_root_for
from backend.agents.social_common.reports import persist_report, quality_block
from backend.agents.social_common.taxonomy import load_taxonomy, match_named, match_topics

logger = logging.getLogger("backend.agents.social_listening")


def _excerpt(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _language(text: str, supplied: str | None) -> str | None:
    if supplied:
        return supplied
    if not text:
        return None
    return "en" if sum(ch.isascii() for ch in text) / max(len(text), 1) > 0.85 else None


def normalize_post(
    post: RawPost,
    *,
    taxonomy: dict,
    config: SocialConfig,
    collected_at: str,
) -> SocialObservation:
    excerpt = _excerpt(post.text, config.excerpt_max_chars)
    method, status = align_published(post.published_at, config)
    brands = taxonomy.get("brands") or {}
    products = taxonomy.get("products") or {}
    competitors = taxonomy.get("competitors") or {}
    categories = taxonomy.get("categories") or {}
    topics = taxonomy.get("topics") or {}
    brand = match_named(excerpt, brands)
    product = match_named(excerpt, products)
    competitor = match_named(excerpt, competitors)
    category = None
    if product and product in products:
        category = products[product].get("category")
    elif brand and brand in brands:
        category = brands[brand].get("category")
    if category is None:
        category = match_named(excerpt, categories)
    obs_id = content_fingerprint(post.source_url, excerpt)[:16]
    confidence = "LOW"
    if post.data_quality == "TEST_FIXTURE":
        confidence = "LOW"
    elif post.published_at and excerpt:
        confidence = "MEDIUM"
    return SocialObservation(
        observation_id=obs_id,
        source=post.source,
        source_type=post.source_type,
        source_url=post.source_url,
        author_id_hash=hash_author(post.author),
        published_at=post.published_at,
        collected_at=collected_at,
        brand=brand,
        category=category,
        product=product,
        competitor=competitor,
        region=post.region,
        country=post.country,
        text_or_excerpt=excerpt,
        language=_language(excerpt, post.language),
        engagement=post.engagement,
        data_quality=post.data_quality,
        confidence=confidence,  # type: ignore[arg-type]
        topics=match_topics(excerpt, topics),
        pos_period_start=config.pos_period_start,
        pos_period_end=config.pos_period_end,
        alignment_method=method,
        alignment_status=status,  # type: ignore[arg-type]
    )


def dedupe(observations: list[SocialObservation]) -> list[SocialObservation]:
    seen_url: set[str] = set()
    seen_fp: set[str] = set()
    unique: list[SocialObservation] = []
    for item in observations:
        url_key = item.source_url.strip().casefold()
        fp = content_fingerprint(item.source_url, item.text_or_excerpt)
        if url_key in seen_url or fp in seen_fp:
            continue
        seen_url.add(url_key)
        seen_fp.add(fp)
        unique.append(item)
    return unique


def run_social_listening(
    input_path: str | Path,
    *,
    config_path: str | Path | None = None,
    taxonomy_path: str | Path | None = None,
    adapters: list[SourceAdapter] | None = None,
    fixture_path: str | Path | None = None,
    write_outputs: bool = True,
) -> SpecialistReport:
    source = Path(input_path).expanduser().resolve()
    config = load_social_config(None if config_path is None else Path(config_path))
    taxonomy = load_taxonomy(None if taxonomy_path is None else Path(taxonomy_path))
    collectors = list(adapters) if adapters is not None else default_live_adapters()
    data_mode: DataMode = "NO_SOCIAL_DATA"
    if fixture_path is not None:
        collectors.append(FixtureAdapter(Path(fixture_path)))
        data_mode = "TEST_FIXTURES_ONLY"
    registry = []
    posts: list[RawPost] = []
    collected_at = datetime_now()
    for adapter in collectors:
        result = adapter.collect()
        registry.append(result.entry)
        posts.extend(result.posts)
    observations = dedupe(
        [normalize_post(post, taxonomy=taxonomy, config=config, collected_at=collected_at) for post in posts]
    )
    live_ok = [entry for entry in registry if entry.status == "AVAILABLE" and entry.source != "test_fixtures"]
    if live_ok and fixture_path is None:
        data_mode = "LIVE" if all(entry.status == "AVAILABLE" for entry in registry) else "PARTIAL_LIVE"
    elif fixture_path is not None:
        data_mode = "TEST_FIXTURES_ONLY"
    elif any(entry.status == "PARTIAL" for entry in registry):
        data_mode = "PARTIAL_LIVE"
    notes = list(config.limitations)
    notes.append("SocialListeningAgent does not bypass authentication, robots.txt, rate limits, or access controls.")
    if data_mode == "NO_SOCIAL_DATA":
        notes.append("No live social source returned observations. Posts were not fabricated.")
    if data_mode == "TEST_FIXTURES_ONLY":
        notes.append("DATA MODE: TEST_FIXTURES_ONLY. Findings are not live social intelligence.")
    sources = sorted({item.source for item in observations})
    status = SocialAgentStatus.READY_WITH_WARNINGS
    if not observations:
        status = SocialAgentStatus.READY_WITH_WARNINGS
    assert_no_causal_language(notes, config)
    quality = quality_block(observations, config, notes)
    report = SpecialistReport(
        agent="SocialListeningAgent",
        status=status,
        data_mode=data_mode,
        period=quality.date_range,
        observations=observations,
        source_registry=registry,
        confidence=quality.confidence,
        sources=sources,
        limitations=notes,
        quality=quality,
    )
    if write_outputs:
        root = data_root_for(source)
        folder = "social_fixture_reports" if data_mode == "TEST_FIXTURES_ONLY" else "social_reports"
        persist_report(report, root / folder / "social_listening_v1.json")
        logger.info(
            "social_listening_written path=%s n=%s mode=%s",
            report.report_output_path,
            len(observations),
            data_mode,
        )
    return report


def datetime_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_listening_report(path: Path) -> SpecialistReport:
    from backend.agents.social_common.paths import read_json

    return SpecialistReport.model_validate(read_json(path, kind="social listening report"))
