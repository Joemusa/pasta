"""Social & Consumer Intelligence V1. Posts are never invented; POS values are never recalculated."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.agents.consumer_needs import run_consumer_needs
from backend.agents.consumer_sentiment import run_consumer_sentiment
from backend.agents.social_brain import run_social_brain
from backend.agents.social_brain.agent import copy_pos_story, relate_theme
from backend.agents.social_common.adapters import (
    CollectionResult,
    FixtureAdapter,
    PublicWebAdapter,
    RedditAdapter,
    SourceAdapter,
    XAdapter,
    YouTubeAdapter,
    default_live_adapters,
)
from backend.agents.social_common.alignment import align_published, split_recent_baseline
from backend.agents.social_common.confidence import insight_confidence
from backend.agents.social_common.hashing import hash_author
from backend.agents.social_common.language import assert_payload_safe
from backend.agents.social_common.models import SocialConfig, SocialObservation, ThemeRecord, load_social_config
from backend.agents.social_common.paths import SocialLoadError
from backend.agents.social_common.sentiment import classify_text, dimension_breakdowns
from backend.agents.social_common.taxonomy import load_taxonomy, match_named, match_needs
from backend.agents.social_common.trends import classify_trend
from backend.agents.social_listening import run_social_listening
from backend.agents.social_trend import run_social_trend
from backend.tests.storytelling_helpers import brain_one_slide, write_one_slide

FIXTURE = Path("backend/tests/fixtures/social/conversations.json")
EMPTY = Path("backend/tests/fixtures/social/empty.json")
DATA_ROOT = Path("backend/data")
BRAIN_JSON = next(Path("backend/data/brain_reports").glob("*.brain.json"))


class ClosedAdapter(SourceAdapter):
    name = "closed"
    source_type = "social"
    access_method = "none"

    def collect(self) -> CollectionResult:
        from backend.agents.social_common.models import SourceRegistryEntry

        return CollectionResult(
            entry=SourceRegistryEntry(
                source=self.name,
                source_type=self.source_type,
                access_method=self.access_method,
                status="UNAVAILABLE",
                last_successful_collection=None,
                limitations=["Adapter closed for tests. Posts were not fabricated."],
            )
        )


def _brain_root(tmp_path: Path) -> Path:
    write_one_slide(tmp_path / "brain_reports" / "panel.brain.json")
    return tmp_path


def _obs(**kwargs) -> SocialObservation:
    payload = {
        "observation_id": kwargs.get("observation_id", "x"),
        "source": kwargs.get("source", "reddit"),
        "source_type": "social",
        "source_url": kwargs.get("source_url", "https://example.test/x"),
        "author_id_hash": kwargs.get("author_id_hash"),
        "published_at": kwargs.get("published_at", "2026-08-01T00:00:00Z"),
        "collected_at": "2026-08-31T00:00:00Z",
        "brand": kwargs.get("brand"),
        "category": kwargs.get("category"),
        "product": kwargs.get("product"),
        "competitor": kwargs.get("competitor"),
        "text_or_excerpt": kwargs.get("text_or_excerpt", "Sunlight"),
        "data_quality": kwargs.get("data_quality", "TEST_FIXTURE"),
        "confidence": kwargs.get("confidence", "LOW"),
        "topics": kwargs.get("topics", []),
        "alignment_status": kwargs.get("alignment_status", "ALIGNED"),
    }
    return SocialObservation.model_validate(payload)


def test_source_provenance(tmp_path: Path) -> None:
    report = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    assert report.observations
    for item in report.observations:
        assert item.source
        assert item.source_url.startswith("https://example.test/")
        assert item.collected_at
        assert item.data_quality == "TEST_FIXTURE"


def test_unavailable_sources() -> None:
    for adapter in default_live_adapters():
        result = adapter.collect()
        assert result.entry.status == "UNAVAILABLE"
        assert result.posts == []
    names = {adapter.name for adapter in default_live_adapters()}
    assert names == {"reddit", "youtube", "x", "public_web"}
    assert RedditAdapter().collect().entry.status == "UNAVAILABLE"
    assert YouTubeAdapter().collect().entry.status == "UNAVAILABLE"
    assert XAdapter().collect().entry.status == "UNAVAILABLE"
    assert PublicWebAdapter().collect().entry.status == "UNAVAILABLE"


def test_empty_datasets(tmp_path: Path) -> None:
    listening = run_social_listening(tmp_path, fixture_path=EMPTY, write_outputs=False)
    assert listening.observations == []
    sentiment = run_consumer_sentiment(tmp_path, listening=listening, write_outputs=False)
    assert sentiment.sentiment is not None
    assert sentiment.sentiment.evidence_count == 0
    assert sentiment.sentiment.share_positive is None
    assert sentiment.sentiment.share_negative is None
    needs = run_consumer_needs(tmp_path, listening=listening, write_outputs=False)
    assert needs.themes == []
    trends = run_social_trend(tmp_path, listening=listening, write_outputs=False)
    assert all(item.status == "INSUFFICIENT_EVIDENCE" for item in trends.signals)


def test_duplicate_urls_and_posts(tmp_path: Path) -> None:
    report = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    urls = [item.source_url for item in report.observations]
    assert len(urls) == len(set(urls))
    assert urls.count("https://example.test/social/avail-01") == 1
    fingerprints = {(item.source_url, item.text_or_excerpt) for item in report.observations}
    assert len(fingerprints) == len(report.observations)


def test_sentiment_classification() -> None:
    tax = load_taxonomy()
    lexicon = tax["sentiment"]
    assert classify_text("I love this, it works great", lexicon)[0] == "POSITIVE"
    assert classify_text("This is terrible and a waste", lexicon)[0] == "NEGATIVE"
    assert classify_text("I bought a bottle yesterday", lexicon)[0] == "NEUTRAL"
    label, intensity = classify_text("I hate this disgusting product", lexicon)
    assert label == "NEGATIVE"
    assert intensity == "HIGH"


def test_mixed_sentiment(tmp_path: Path) -> None:
    tax = load_taxonomy()
    label, _intensity = classify_text(
        "I love the Sunlight fragrance but it's expensive and I'm disappointed",
        tax["sentiment"],
    )
    assert label == "MIXED"
    report = run_consumer_sentiment(
        tmp_path,
        listening=run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False),
        write_outputs=False,
    )
    assert report.sentiment is not None
    assert report.sentiment.share_mixed is not None
    assert report.sentiment.share_mixed > 0
    for key in ("price", "availability", "product", "brand", "promotion", "service"):
        assert key in report.sentiment_by_dimension


def test_theme_extraction(tmp_path: Path) -> None:
    listening = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    needs = run_consumer_needs(tmp_path, listening=listening, write_outputs=False)
    names = {item.theme for item in needs.themes}
    assert "availability" in names
    assert "affordability" in names or "value_for_money" in names
    assert "convenience" not in names
    availability = next(item for item in needs.themes if item.theme == "availability")
    assert availability.frequency >= 2
    assert availability.representative_evidence
    assert availability.brands_affected
    assert availability.sources
    assert "commercial action" in availability.consumer_implication.lower()
    assert "increase distribution" not in availability.consumer_implication.lower()


def test_trend_detection_and_insufficient_history(tmp_path: Path) -> None:
    listening = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    trends = run_social_trend(tmp_path, listening=listening, write_outputs=False)
    by_name = {item.name: item for item in trends.signals}
    assert by_name["availability_complaints"].status in {"EMERGING", "GROWING"}
    assert by_name["availability_complaints"].baseline_count >= 1
    assert by_name["availability_complaints"].recent_count >= 5
    assert any(item.status == "INSUFFICIENT_EVIDENCE" for item in trends.signals)
    config = load_social_config()
    assert classify_trend(2, 1, config) == "INSUFFICIENT_EVIDENCE"
    assert classify_trend(8, 4, config) == "GROWING"
    assert classify_trend(5, 0, config) == "INSUFFICIENT_EVIDENCE"
    fat = SocialConfig(trend_min_total=5, trend_min_recent=5, trend_growth_ratio=1.5)
    assert classify_trend(5, 0, fat) == "EMERGING"
    assert classify_trend(5, 5, fat) == "STABLE"
    assert classify_trend(2, 8, fat) == "DECLINING"


def test_source_diversity_and_confidence() -> None:
    config = load_social_config()
    one = [_obs(source="reddit", observation_id="1")]
    assert insight_confidence(one, config) == "LOW"
    many_one_source = [
        _obs(source="reddit", observation_id=str(i), source_url=f"https://example.test/{i}") for i in range(20)
    ]
    assert insight_confidence(many_one_source, config) == "MEDIUM"
    diverse = [
        _obs(source=src, observation_id=f"{src}-{i}", source_url=f"https://example.test/{src}/{i}")
        for src in ("reddit", "youtube", "public_web")
        for i in range(8)
    ]
    assert insight_confidence(diverse, config) == "HIGH"
    assert insight_confidence([], config) == "LOW"


def test_date_alignment_and_future_leakage(tmp_path: Path) -> None:
    config = load_social_config()
    method, status = align_published("2026-08-10T00:00:00Z", config)
    assert status == "ALIGNED"
    assert "pos_period" in method
    _method, future = align_published("2026-08-25T00:00:00Z", config)
    assert future == "FUTURE_LEAKAGE"
    _method, missing = align_published(None, config)
    assert missing == "INSUFFICIENT_DATES"
    report = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    future_rows = [item for item in report.observations if item.alignment_status == "FUTURE_LEAKAGE"]
    assert future_rows
    assert all(item.published_at and item.published_at[:10] > config.pos_period_end for item in future_rows)
    recent, baseline = split_recent_baseline(report.observations, config)
    assert all((item.published_at or "")[:10] <= config.pos_period_end for item in recent + baseline)
    sentiment = run_consumer_sentiment(tmp_path, listening=report, write_outputs=False)
    assert any("FUTURE_LEAKAGE" in note for note in sentiment.limitations)


def test_anonymous_author_handling(tmp_path: Path) -> None:
    assert hash_author("jane_doe") == f"anon_{hashlib.sha256(b'jane_doe').hexdigest()[:16]}"
    assert hash_author("anonymous") is None
    assert hash_author("[deleted]") is None
    assert hash_author(None) is None
    report = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    hashes = {item.author_id_hash for item in report.observations}
    blob = json.dumps(report.to_json_dict())
    assert "shelf_watcher" not in blob
    assert "jane_doe" not in blob
    assert any(value is None for value in hashes)
    assert any(value and value.startswith("anon_") for value in hashes)


def test_missing_fields_are_not_zero(tmp_path: Path) -> None:
    report = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    missing = next(item for item in report.observations if item.source_url.endswith("missing-01"))
    assert missing.published_at is None
    assert missing.author_id_hash is None
    assert missing.region is None
    assert missing.engagement is None
    assert missing.alignment_status == "INSUFFICIENT_DATES"
    empty = run_consumer_sentiment(
        tmp_path,
        listening=run_social_listening(tmp_path, fixture_path=EMPTY, write_outputs=False),
        write_outputs=False,
    )
    assert empty.sentiment is not None
    assert empty.sentiment.share_positive is None
    assert empty.sentiment.positive_negative_ratio is None
    dims = dimension_breakdowns([], load_taxonomy()["sentiment"])
    assert dims["price"].share_negative is None
    assert dims["price"].evidence_count == 0


def test_brand_category_competitor_classification(tmp_path: Path) -> None:
    tax = load_taxonomy()
    assert match_named("Sunlight Pine Gel at Shoprite", tax["brands"]) == "Sunlight"
    assert match_named("Sunlight Pine Gel 500ml", tax["products"]) == "Sunlight Pine Gel"
    assert match_named("switched to Dettol", tax["competitors"]) == "Dettol"
    assert match_named("I surf every weekend", tax["brands"]) is None
    assert match_named("dove chocolate", tax["brands"]) is None
    assert match_named("Omo laundry detergent", tax["brands"]) == "Omo"
    report = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    brands = {item.brand for item in report.observations if item.brand}
    categories = {item.category for item in report.observations if item.category}
    competitors = {item.competitor for item in report.observations if item.competitor}
    assert "Sunlight" in brands
    assert "Handy Andy" in brands
    assert "Home Care" in categories
    assert "Ice Cream" in categories
    assert {"Dettol", "Ariel", "Fairy"} <= competitors
    extra = {"NewBrand": {"aliases": ["newbrand"], "category": "Home Care"}}
    assert match_named("I bought NewBrand cleaner", extra) == "NewBrand"


def test_pos_integration_and_brain_not_modified(tmp_path: Path) -> None:
    root = _brain_root(tmp_path)
    before = (root / "brain_reports" / "panel.brain.json").read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    report = run_social_brain(root, fixture_path=FIXTURE, write_outputs=True)
    after = (root / "brain_reports" / "panel.brain.json").read_bytes()
    assert hashlib.sha256(after).hexdigest() == digest
    payload = json.loads(after)
    assert payload["total_addressable_value_opportunity"] == pytest.approx(588562.67)
    assert payload["total_addressable_volume_opportunity"] == pytest.approx(14521.165)
    assert report.pos_story.total_addressable_value_opportunity == pytest.approx(588562.67)
    assert report.pos_story.total_addressable_volume_opportunity == pytest.approx(14521.165)
    assert report.pos_story.dominant_lever == "DISTRIBUTION"
    assert report.verdict == "SUPPORTS"
    assert report.data_mode == "TEST_FIXTURES_ONLY"
    assert (root / "social_fixture_reports" / "social_context_brain_v1.json").is_file()


def test_commercial_brain_file_on_disk_unchanged_by_live_run() -> None:
    before = BRAIN_JSON.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    report = run_social_brain(DATA_ROOT, write_outputs=True)
    assert hashlib.sha256(BRAIN_JSON.read_bytes()).hexdigest() == digest
    assert report.data_mode in {"NO_SOCIAL_DATA", "PARTIAL_LIVE"}
    assert report.pos_story.total_addressable_value_opportunity == pytest.approx(588562.67)
    payload = json.loads(BRAIN_JSON.read_text(encoding="utf-8"))
    assert payload["total_addressable_value_opportunity"] == pytest.approx(588562.67)
    for action in payload["top_actions"][:3]:
        assert action["confidence"] in {"HIGH", "MEDIUM", "LOW"}


def test_no_causal_claims_or_commercial_actions(tmp_path: Path) -> None:
    root = _brain_root(tmp_path)
    report = run_social_brain(root, fixture_path=FIXTURE, write_outputs=False)
    blob = json.dumps(report.to_json_dict()).lower()
    assert "will increase" not in blob
    assert "proof that" not in blob
    assert "increase distribution" not in blob
    assert "cut the price" not in blob
    assert report.causality_claim == "none"
    assert_payload_safe(report.to_json_dict())
    for item in report.commercial_context:
        assert "increase distribution" not in item.statement.lower()


def test_no_fabricated_observations(tmp_path: Path) -> None:
    live = run_social_listening(tmp_path, adapters=default_live_adapters(), write_outputs=False)
    assert live.observations == []
    assert live.data_mode == "NO_SOCIAL_DATA"
    assert all(entry.status == "UNAVAILABLE" for entry in live.source_registry)
    joined = " ".join(live.limitations).lower()
    assert "not fabricated" in joined or "never invented" in joined
    closed = run_social_listening(tmp_path, adapters=[ClosedAdapter()], write_outputs=False)
    assert closed.observations == []
    fixture = run_social_listening(tmp_path, fixture_path=FIXTURE, write_outputs=False)
    assert all(item.data_quality == "TEST_FIXTURE" for item in fixture.observations)
    assert fixture.data_mode == "TEST_FIXTURES_ONLY"


def test_fixture_rejects_unlabeled_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"posts": [{"source_url": "https://example.test/x", "text": "hi"}]}), encoding="utf-8")
    with pytest.raises(SocialLoadError, match="TEST_FIXTURES_ONLY"):
        FixtureAdapter(path).collect()


def test_social_context_brain_supports_distribution_gap() -> None:
    theme = ThemeRecord(
        theme="availability",
        frequency=8,
        sentiment="NEGATIVE",
        consumer_implication="Consumer conversations contain recurring availability complaints.",
        confidence="MEDIUM",
        commercial_levers=["DISTRIBUTION"],
        channels=["AVAILABILITY"],
    )
    aligned = relate_theme(theme, "DISTRIBUTION")
    assert aligned.relation == "SUPPORTS"
    expensive = ThemeRecord(
        theme="affordability",
        frequency=3,
        sentiment="NEGATIVE",
        consumer_implication="Consumers discuss affordability.",
        confidence="LOW",
        commercial_levers=["PRICE"],
        channels=["CONSUMER_AFFORDABILITY"],
    )
    assert relate_theme(expensive, "PRICE").relation == "ADD_CONTEXT"
    easy = ThemeRecord(
        theme="availability",
        frequency=4,
        sentiment="POSITIVE",
        consumer_implication="Consumers say it is easy to find.",
        confidence="LOW",
        commercial_levers=["DISTRIBUTION"],
        channels=["AVAILABILITY"],
    )
    assert relate_theme(easy, "DISTRIBUTION").relation == "CONTRADICTS"


def test_needs_require_observations() -> None:
    tax = load_taxonomy()
    assert match_needs("random small talk about the weather", tax) == []
    assert "availability" in match_needs("Can't find Sunlight, out of stock", tax)


def test_copy_pos_story_does_not_recalculate() -> None:
    slide = brain_one_slide()
    copied = copy_pos_story(slide, Path("backend/data/brain_reports/panel.brain.json"))
    assert copied.total_addressable_value_opportunity == slide["total_addressable_value_opportunity"]
    assert copied.total_addressable_volume_opportunity == slide["total_addressable_volume_opportunity"]
    assert copied.n_actions == 3


def test_empty_dimension_shares_stay_missing() -> None:
    dims = dimension_breakdowns([], load_taxonomy()["sentiment"])
    for block in dims.values():
        assert block.share_positive is None
        assert block.evidence_count == 0
