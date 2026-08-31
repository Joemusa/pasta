"""GDELT live-validation helpers. Tests inject collected results and do not call the network."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.agents.social_common.adapters import CollectionResult, PublicWebAdapter, RawPost
from backend.agents.social_common.gdelt_validation import (
    SMOKE_SPEC_PATH,
    ReplayAdapter,
    drop_future_and_duplicates,
    render_validation_report,
    run_gdelt_validation,
    unavailable_result,
)
from backend.agents.social_common.models import SourceRegistryEntry
from backend.agents.social_common.queries import expand_search_queries, load_query_spec
from backend.tests.storytelling_helpers import write_one_slide

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def _entry(**kwargs) -> SourceRegistryEntry:
    payload = {
        "source": "public_web",
        "source_type": "web",
        "access_method": "gdelt_doc_2_0_api",
        "status": "AVAILABLE",
        "record_count": 0,
        "error": None,
        "limitations": ["injected test collection"],
    }
    payload.update(kwargs)
    return SourceRegistryEntry.model_validate(payload)


def _post(**kwargs) -> RawPost:
    payload = {
        "source": "public_web",
        "source_type": "news",
        "source_url": "https://news.example/unilever-za",
        "author": None,
        "published_at": "2026-08-10T10:15:00Z",
        "text": "Unilever granted extension to change Sunlight dishwashing packaging",
        "country": "ZA",
        "data_quality": "LIVE",
    }
    payload.update(kwargs)
    return RawPost(**payload)


def _brain_root(tmp_path: Path) -> Path:
    write_one_slide(tmp_path / "brain_reports" / "panel.brain.json")
    return tmp_path


def test_smoke_spec_is_http_gdelt_without_newsapi() -> None:
    spec = load_query_spec(SMOKE_SPEC_PATH)
    assert spec["public_web"]["gdelt"]["enabled"] is True
    assert spec["public_web"]["gdelt"]["endpoint"].startswith("http://api.gdeltproject.org/")
    assert spec["public_web"]["newsapi"]["enabled"] is False
    assert spec["south_africa"]["boost_first_n"] == 0
    queries = expand_search_queries(spec, source="public_web")
    terms = {item.term for item in queries}
    for name in ["Unilever", "Sunlight", "Omo", "Domestos", "Handy Andy", "Knorr", "Dove", "Vaseline", "FMCG"]:
        assert name in terms
    assert any("sourcecountry:SouthAfrica" in item.text for item in queries)
    assert any("price" in item.text.lower() for item in queries)
    texts = [item.text.lower() for item in queries]
    assert any("household spending" in text or "consumer behaviour" in text for text in texts)


def test_drop_future_duplicates_and_window() -> None:
    posts = [
        _post(),
        _post(source_url="https://news.example/unilever-za", text="duplicate url"),
        _post(
            source_url="https://news.example/same-title",
            text="Unilever granted extension to change Sunlight dishwashing packaging",
        ),
            _post(
                source_url="https://news.example/future",
                published_at="2026-09-15T00:00:00Z",
                text="Future Unilever announcement",
            ),
            _post(
                source_url="https://news.example/old",
                published_at="2025-01-01T00:00:00Z",
                text="Old Unilever announcement",
            ),
        _post(source_url="https://news.example/undated", published_at=None, country=None, text="Unilever review"),
    ]
    kept, stats = drop_future_and_duplicates(posts, now=NOW)
    urls = [item.source_url for item in kept]
    assert "https://news.example/unilever-za" in urls
    assert "https://news.example/undated" in urls
    assert "https://news.example/future" not in urls
    assert "https://news.example/old" not in urls
    assert "https://news.example/same-title" not in urls
    assert stats["duplicate_url"] == 1
    assert stats["duplicate_content"] == 1
    assert stats["future"] == 1
    assert stats["outside_window"] == 1
    assert stats["kept"] == 2


def test_failed_gdelt_does_not_substitute_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("backend.agents.social_common.gdelt_validation.collect_gdelt_live", _boom)
    summary = run_gdelt_validation(
        tmp_path,
        collected=unavailable_result("ssl handshake timeout"),
        write_outputs=True,
    )
    assert summary["connection"] == "FAILED"
    assert summary["live_data_status"] == "UNAVAILABLE"
    assert summary["records_retrieved"] == 0
    assert "UNAVAILABLE" in summary["report_text"]
    assert "ssl handshake timeout" in summary["report_text"]
    payload = (tmp_path / "social_live_validation" / "gdelt_smoke_summary.json").read_text(encoding="utf-8")
    assert "TEST_FIXTURE" not in payload
    assert "LIVE — GDELT" not in payload


def test_fixture_records_are_rejected(tmp_path: Path) -> None:
    collected = CollectionResult(
        entry=_entry(record_count=1),
        posts=[_post(data_quality="TEST_FIXTURE")],
    )
    with pytest.raises(RuntimeError, match="Fixture records"):
        run_gdelt_validation(tmp_path, collected=collected, write_outputs=False)


def test_live_replay_normalises_and_analyses_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("backend.agents.social_common.gdelt_validation.collect_gdelt_live", _boom)
    root = _brain_root(tmp_path)
    collected = CollectionResult(
        entry=_entry(record_count=4),
        posts=[
            _post(),
            _post(source_url="https://news.example/unilever-za", text="duplicate url"),
            _post(
                source_url="https://news.example/us",
                text="Unilever quarterly results in New York",
                country="US",
                published_at="2026-08-12T00:00:00Z",
            ),
            _post(
                source_url="https://news.example/unknown",
                text="Household spending and promotions discussed",
                country=None,
                published_at="2026-08-08T00:00:00Z",
            ),
        ],
    )
    summary = run_gdelt_validation(root, collected=collected, write_outputs=True)
    assert summary["connection"] == "SUCCESS"
    assert summary["live_data_status"] == "LIVE — GDELT"
    assert summary["records_retrieved"] == 4
    assert summary["records_after_deduplication"] == 3
    assert summary["records_successfully_normalised"] == 3
    assert summary["records_successfully_analysed"] == 3
    assert "Sunlight" in summary["top_brands_detected"]
    assert summary["south_africa_specific_records"] == 1
    assert summary["unknown_geography_records"] == 1
    assert summary["other_geography_records"] == 1
    assert all(url.startswith("https://news.example/") for url in summary["source_urls"])
    assert "TEST_FIXTURE" not in summary["report_text"]
    listening = root / "social_live_validation" / "social_listening_v1.json"
    assert listening.is_file()
    blob = listening.read_text(encoding="utf-8")
    assert '"data_quality": "LIVE"' in blob
    assert "TEST_FIXTURE" not in blob
    assert (root / "social_live_validation" / "social_context_brain_v1.json").is_file()


def test_replay_adapter_does_not_invent_posts() -> None:
    original = CollectionResult(entry=_entry(record_count=1), posts=[_post()])
    replayed = ReplayAdapter(original).collect()
    assert replayed.posts[0].source_url == original.posts[0].source_url
    assert replayed.posts[0].data_quality == "LIVE"
    assert replayed.entry.record_count == 1
    replayed.posts.clear()
    assert original.posts


def test_render_unavailable_status() -> None:
    text = render_validation_report(
        {
            "connection": "FAILED",
            "live_data_status": "UNAVAILABLE",
            "records_retrieved": 0,
            "records_after_deduplication": 0,
            "records_successfully_normalised": 0,
            "records_successfully_analysed": 0,
            "data_quality_issues": ["GDELT timeout"],
        }
    )
    assert "Connection: FAILED" in text
    assert "LIVE DATA STATUS = UNAVAILABLE" in text


def test_public_web_skips_live_http_during_pytest() -> None:
    result = PublicWebAdapter(spec=load_query_spec(SMOKE_SPEC_PATH), env={}).collect()
    assert result.posts == []
    assert result.entry.status == "UNAVAILABLE"
    assert result.entry.error
    assert "SOCIAL_LIVE_NETWORK" in (result.entry.error or "")
