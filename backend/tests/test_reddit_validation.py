"""Reddit live-validation helpers. Tests inject collected results and do not call the network."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.social_common.adapters import CollectionResult, RawPost, RedditAdapter
from backend.agents.social_common.models import SourceRegistryEntry
from backend.agents.social_common.queries import expand_search_queries, load_query_spec
from backend.agents.social_common.reddit_validation import (
    SMOKE_SPEC_PATH,
    render_reddit_report,
    run_reddit_validation,
    subreddit_from_url,
    unavailable_reddit,
)
from backend.tests.storytelling_helpers import write_one_slide
from backend.tests.test_social_live_adapters import FakeHttp, _json, _spec


def _entry(**kwargs) -> SourceRegistryEntry:
    payload = {
        "source": "reddit",
        "source_type": "social",
        "access_method": "official_oauth_api",
        "status": "AVAILABLE",
        "record_count": 0,
        "error": None,
        "limitations": ["injected test collection"],
    }
    payload.update(kwargs)
    return SourceRegistryEntry.model_validate(payload)


def _post(**kwargs) -> RawPost:
    payload = {
        "source": "reddit",
        "source_type": "social",
        "source_url": "https://www.reddit.com/r/southafrica/comments/abc/sunlight/",
        "author": "visible_handle",
        "published_at": "2026-08-10T10:15:00Z",
        "text": "Sunlight dishwashing is expensive at Shoprite but still works",
        "country": "ZA",
        "data_quality": "LIVE",
    }
    payload.update(kwargs)
    return RawPost(**payload)


def _brain_root(tmp_path: Path) -> Path:
    write_one_slide(tmp_path / "brain_reports" / "panel.brain.json")
    return tmp_path


def test_smoke_spec_covers_unilever_brands_and_consumer_themes() -> None:
    spec = load_query_spec(SMOKE_SPEC_PATH)
    assert spec["south_africa"]["boost_first_n"] == 0
    queries = expand_search_queries(spec, source="reddit")
    blob = " ".join(item.text.lower() for item in queries)
    for name in ["unilever", "sunlight", "omo", "domestos", "handy andy", "knorr", "dove", "vaseline"]:
        assert name in blob
    for theme in ["price", "afford", "promo", "out of stock", "quality", "laundry", "personal care"]:
        assert theme in blob
    assert any("subreddit:southafrica" in item.text.lower() for item in queries)


def test_subreddit_from_url() -> None:
    assert subreddit_from_url("https://www.reddit.com/r/southafrica/comments/abc/sunlight/") == "southafrica"
    assert subreddit_from_url("https://example.test/not-reddit") is None


def test_failed_reddit_does_not_substitute_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("backend.agents.social_common.reddit_validation.collect_reddit_live", _boom)
    summary = run_reddit_validation(
        tmp_path,
        collected=unavailable_reddit("OAuth credentials were not provided. Set REDDIT_CLIENT_ID."),
        write_outputs=True,
    )
    assert summary["connection"] == "FAILED"
    assert summary["reddit_live_status"] == "UNAVAILABLE"
    assert summary["records_retrieved"] == 0
    assert "UNAVAILABLE" in summary["report_text"]
    assert "TEST_FIXTURE" not in summary["report_text"]
    assert "LIVE — REDDIT" not in Path(
        tmp_path / "social_live_validation" / "reddit_smoke_summary.json"
    ).read_text(encoding="utf-8")


def test_fixture_records_are_rejected(tmp_path: Path) -> None:
    collected = CollectionResult(entry=_entry(record_count=1), posts=[_post(data_quality="TEST_FIXTURE")])
    with pytest.raises(RuntimeError, match="Fixture records"):
        run_reddit_validation(tmp_path, collected=collected, write_outputs=False)


def test_live_reddit_replay_anonymises_and_analyses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("backend.agents.social_common.reddit_validation.collect_reddit_live", _boom)
    root = _brain_root(tmp_path)
    collected = CollectionResult(
        entry=_entry(record_count=3),
        posts=[
            _post(),
            _post(
                source_url="https://www.reddit.com/r/southafrica/comments/abc/sunlight/",
                text="duplicate url",
            ),
            _post(
                source_url="https://www.reddit.com/r/worldnews/comments/zz/unilever/",
                text="Unilever quarterly results discussion",
                country=None,
                author="other_handle",
                published_at="2026-08-08T00:00:00Z",
            ),
        ],
    )
    summary = run_reddit_validation(root, collected=collected, write_outputs=True)
    assert summary["connection"] == "SUCCESS"
    assert summary["reddit_live_status"] == "LIVE"
    assert summary["records_retrieved"] == 3
    assert summary["records_after_deduplication"] == 2
    assert summary["south_africa_specific_records"] == 1
    assert summary["unknown_geography_records"] == 1
    assert summary["records_by_brand"].get("Sunlight") == 1
    assert "southafrica" in summary["source_subreddit_distribution"]
    blob = str(summary)
    assert "visible_handle" not in blob
    assert "other_handle" not in blob
    for row in summary["observations"]:
        assert row["data_quality"] == "LIVE"
        assert row["source_url"]
        assert row["published_at"]
        assert row["collected_at"]
        assert row["author_hash"]
        assert row["author_hash"].startswith("anon_")
        assert "sentiment" in row
        assert "themes" in row
        assert "author" not in row
    report = (root / "social_live_validation" / "reddit" / "social_listening_v1.json").read_text(encoding="utf-8")
    assert "visible_handle" not in report
    assert '"data_quality": "LIVE"' in report


def test_reddit_adapter_unavailable_without_credentials_during_pytest() -> None:
    result = RedditAdapter(spec=load_query_spec(SMOKE_SPEC_PATH), env={}).collect()
    assert result.posts == []
    assert result.entry.status == "UNAVAILABLE"
    assert "REDDIT_CLIENT_ID" in (result.entry.error or "")


def test_render_unavailable_status() -> None:
    text = render_reddit_report({"reddit_live_status": "UNAVAILABLE", "records_retrieved": 0})
    assert "REDDIT LIVE STATUS = UNAVAILABLE" in text


def test_injected_http_does_not_store_usernames() -> None:
    http = FakeHttp(
        {
            ("POST", "access_token"): _json({"access_token": "tok"}),
            ("GET", "oauth.reddit.com/search"): _json(
                {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "permalink": "/r/southafrica/comments/xy/post/",
                                    "subreddit": "southafrica",
                                    "title": "Sunlight dishwashing review",
                                    "selftext": "works at Shoprite",
                                    "author": "do_not_persist",
                                    "created_utc": 1754006400,
                                    "score": 3,
                                }
                            }
                        ]
                    }
                }
            ),
        }
    )
    result = RedditAdapter(
        http=http,
        env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"},
        spec=_spec(),
    ).collect()
    assert result.posts[0].author == "do_not_persist"
    assert result.posts[0].country == "ZA"
