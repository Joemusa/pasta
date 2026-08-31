"""Live source adapters. Posts are never invented; credentials are never faked."""

from __future__ import annotations

import json
from pathlib import Path

from backend.agents.social_common.adapters import (
    FixtureAdapter,
    PublicWebAdapter,
    RedditAdapter,
    YouTubeAdapter,
    classify_source_class,
)
from backend.agents.social_common.http_client import HttpError, HttpResponse
from backend.agents.social_common.queries import expand_search_queries, load_query_spec
from backend.agents.social_common.taxonomy import load_taxonomy
from backend.agents.social_listening import run_social_listening

FIXTURE = Path("backend/tests/fixtures/social/conversations.json")


class FakeHttp:
    def __init__(self, routes: dict[tuple[str, str], HttpResponse | Exception]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    def get(self, url: str, *, headers: dict | None = None) -> HttpResponse:
        del headers
        return self.request("GET", url)

    def post(self, url: str, data: bytes, *, headers: dict | None = None) -> HttpResponse:
        del data, headers
        return self.request("POST", url)

    def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
        del kwargs
        self.calls.append((method, url))
        for (want_method, part), result in self.routes.items():
            if want_method == method and part in url:
                if isinstance(result, Exception):
                    raise result
                return result
        return HttpResponse(404, "{}", url=url)


def _json(payload: dict | str, url: str = "https://example.test") -> HttpResponse:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return HttpResponse(200, body, url=url)


def _spec() -> dict:
    spec = load_query_spec()
    spec["max_queries_per_source"] = 2
    spec["rate_limit_sleep_seconds"] = 0
    spec["max_youtube_comment_threads"] = 2
    return spec


def test_reddit_unavailable_without_credentials() -> None:
    result = RedditAdapter(env={}, spec=_spec()).collect()
    assert result.entry.status == "UNAVAILABLE"
    assert result.posts == []
    assert result.entry.record_count == 0
    assert result.entry.error
    assert "REDDIT_CLIENT_ID" in (result.entry.error or "")


def test_reddit_adapter_parses_official_search() -> None:
    http = FakeHttp(
        {
            ("POST", "access_token"): _json({"access_token": "tok"}),
            ("GET", "oauth.reddit.com/search"): _json(
                {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "permalink": "/r/southafrica/comments/abc/sunlight/",
                                    "title": "Sunlight dishwashing in Shoprite",
                                    "selftext": "Can't find it.",
                                    "author": "shelf_user",
                                    "created_utc": 1754006400,
                                    "score": 4,
                                }
                            },
                            {
                                "data": {
                                    "permalink": "/r/southafrica/comments/abc/sunlight/",
                                    "title": "duplicate url",
                                    "selftext": "ignored",
                                    "author": "other",
                                    "created_utc": 1754006400,
                                    "score": 1,
                                }
                            },
                            {
                                "data": {
                                    "permalink": "/r/test/comments/del/gone/",
                                    "title": "[deleted]",
                                    "selftext": "",
                                    "author": "[deleted]",
                                    "created_utc": 1754006400,
                                }
                            },
                            {
                                "data": {
                                    "permalink": "/r/test/comments/nodate/",
                                    "title": "Unilever results discussion",
                                    "selftext": "",
                                    "author": "anon",
                                }
                            },
                        ]
                    }
                }
            ),
        }
    )
    result = RedditAdapter(
        http=http, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"}, spec=_spec()
    ).collect()
    assert result.entry.status == "AVAILABLE"
    assert result.entry.record_count == 2
    urls = [item.source_url for item in result.posts]
    assert len(urls) == len(set(urls))
    assert result.posts[0].data_quality == "LIVE"
    assert result.posts[0].source_url.startswith("https://www.reddit.com/")
    assert result.posts[0].published_at
    za = next(item for item in result.posts if item.source_url.endswith("sunlight/"))
    assert za.country == "ZA"
    assert za.region is None
    assert za.engagement == 4
    missing = next(item for item in result.posts if item.source_url.endswith("nodate/"))
    assert missing.published_at is None
    assert all("[deleted]" not in item.text for item in result.posts)


def test_reddit_api_error_and_rate_limit() -> None:
    http = FakeHttp({("POST", "access_token"): HttpError("http_401", status_code=401)})
    failed = RedditAdapter(
        http=http, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"}, spec=_spec()
    ).collect()
    assert failed.entry.status == "UNAVAILABLE"
    assert failed.posts == []
    assert failed.entry.error
    limited = FakeHttp(
        {
            ("POST", "access_token"): _json({"access_token": "tok"}),
            ("GET", "oauth.reddit.com/search"): HttpError("rate_limited", status_code=429, retryable=True),
        }
    )
    result = RedditAdapter(
        http=limited, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"}, spec=_spec()
    ).collect()
    assert result.entry.status == "UNAVAILABLE"
    assert result.entry.error
    assert "429" in (result.entry.error or "") or "rate" in (result.entry.error or "")


def test_youtube_unavailable_without_key() -> None:
    result = YouTubeAdapter(env={}, spec=_spec()).collect()
    assert result.entry.status == "UNAVAILABLE"
    assert result.posts == []
    assert "YOUTUBE_API_KEY" in (result.entry.error or "")


def test_youtube_search_and_comments() -> None:
    http = FakeHttp(
        {
            ("GET", "youtube/v3/search"): _json(
                {
                    "items": [
                        {
                            "id": {"videoId": "vid1"},
                            "snippet": {
                                "title": "Sunlight review",
                                "description": "Home care comparison",
                                "channelTitle": "ReviewChannel",
                                "publishedAt": "2026-08-01T12:00:00Z",
                            },
                        }
                    ]
                }
            ),
            ("GET", "commentThreads"): _json(
                {
                    "items": [
                        {
                            "id": "c1",
                            "snippet": {
                                "topLevelComment": {
                                    "snippet": {
                                        "textDisplay": "Too expensive in Shoprite",
                                        "authorDisplayName": "yt_user",
                                        "publishedAt": "2026-08-02T12:00:00Z",
                                        "likeCount": 3,
                                    }
                                }
                            },
                        },
                        {
                            "id": "c2",
                            "snippet": {
                                "topLevelComment": {
                                    "snippet": {
                                        "textDisplay": "[deleted]",
                                        "authorDisplayName": "gone",
                                    }
                                }
                            },
                        },
                    ]
                }
            ),
        }
    )
    result = YouTubeAdapter(http=http, env={"YOUTUBE_API_KEY": "k"}, spec=_spec()).collect()
    assert result.entry.status == "AVAILABLE"
    assert result.entry.record_count == 2
    video = next(item for item in result.posts if item.source_type == "social")
    comment = next(item for item in result.posts if item.source_type == "social_comment")
    assert video.source_url == "https://www.youtube.com/watch?v=vid1"
    assert video.published_at == "2026-08-01T12:00:00Z"
    assert video.country is None
    assert comment.engagement == 3
    assert comment.data_quality == "LIVE"
    assert all(item.text != "[deleted]" for item in result.posts)


def test_youtube_api_error() -> None:
    http = FakeHttp({("GET", "youtube/v3/search"): HttpError("http_403", status_code=403)})
    result = YouTubeAdapter(http=http, env={"YOUTUBE_API_KEY": "k"}, spec=_spec()).collect()
    assert result.entry.status == "UNAVAILABLE"
    assert result.posts == []


def test_public_web_gdelt_and_duplicates() -> None:
    http = FakeHttp(
        {
            ("GET", "gdeltproject.org"): _json(
                {
                    "articles": [
                        {
                            "url": "https://news.example/unilever-za",
                            "title": "Unilever South Africa price discussion",
                            "seendate": "20260810T101500Z",
                            "language": "English",
                            "sourcecountry": "South Africa",
                        },
                        {
                            "url": "https://news.example/unilever-za",
                            "title": "duplicate",
                            "seendate": "20260810T101500Z",
                            "sourcecountry": "South Africa",
                        },
                        {
                            "url": "https://news.example/unilever-undated",
                            "title": "Unilever brand review",
                            "seendate": "",
                            "sourcecountry": "",
                        },
                    ]
                }
            )
        }
    )
    result = PublicWebAdapter(http=http, env={}, spec=_spec()).collect()
    assert result.entry.status == "AVAILABLE"
    assert result.entry.record_count == 2
    assert result.entry.access_method.startswith("gdelt")
    urls = [item.source_url for item in result.posts]
    assert len(urls) == len(set(urls))
    za = next(item for item in result.posts if item.source_url.endswith("unilever-za"))
    assert za.country == "ZA"
    assert za.published_at == "2026-08-10T10:15:00Z"
    assert za.data_quality == "LIVE"
    assert za.region is None
    undated = next(item for item in result.posts if item.source_url.endswith("undated"))
    assert undated.published_at is None
    assert undated.country is None


def test_public_web_empty_and_errors() -> None:
    blank = PublicWebAdapter(
        http=FakeHttp({("GET", "gdeltproject.org"): _json({"articles": []})}), env={}, spec=_spec()
    ).collect()
    assert blank.posts == []
    assert blank.entry.status == "AVAILABLE"
    assert blank.entry.record_count == 0
    timed = PublicWebAdapter(
        http=FakeHttp({("GET", "gdeltproject.org"): HttpError("timeout", retryable=True)}),
        env={},
        spec=_spec(),
    ).collect()
    assert timed.entry.status == "UNAVAILABLE"
    assert timed.posts == []
    assert timed.entry.error
    limited = PublicWebAdapter(
        http=FakeHttp({("GET", "gdeltproject.org"): HttpError("rate_limited", status_code=429, retryable=True)}),
        env={},
        spec=_spec(),
    ).collect()
    assert limited.entry.status == "UNAVAILABLE"
    assert limited.entry.error


def test_newsapi_optional_official_endpoint() -> None:
    http = FakeHttp(
        {
            ("GET", "gdeltproject.org"): _json({"articles": []}),
            ("GET", "newsapi.org"): _json(
                {
                    "status": "ok",
                    "articles": [
                        {
                            "url": "https://news.example/promo",
                            "title": "Unilever promotion",
                            "description": "Specials this week",
                            "publishedAt": "2026-08-05T00:00:00Z",
                            "author": "reporter",
                        }
                    ],
                }
            ),
        }
    )
    result = PublicWebAdapter(http=http, env={"NEWS_API_KEY": "k"}, spec=_spec()).collect()
    assert any(item.source_url.endswith("/promo") for item in result.posts)
    assert result.entry.status == "AVAILABLE"


def test_queries_come_from_yaml_taxonomy() -> None:
    spec = load_query_spec()
    taxonomy = dict(load_taxonomy())
    taxonomy["brands"] = dict(taxonomy.get("brands") or {})
    taxonomy["brands"]["NewBrand"] = {"aliases": ["newbrand"], "category": "Home Care"}
    brand_queries = expand_search_queries(
        {
            **spec,
            "max_queries_per_source": 50,
            "social_queries": [{"id": "brand", "type": "brand", "from_taxonomy": "brands", "template": "{name}"}],
            "south_africa": {"boost_first_n": 0, "query_boosts": {}},
        },
        taxonomy,
        source="reddit",
    )
    assert any(item.term == "NewBrand" for item in brand_queries)
    assert any(item.term == "Sunlight" for item in brand_queries)


def test_live_fixture_separation(tmp_path: Path) -> None:
    http = FakeHttp(
        {
            ("GET", "gdeltproject.org"): _json(
                {
                    "articles": [
                        {
                            "url": "https://news.example/live-only",
                            "title": "Unilever live article",
                            "seendate": "20260801T000000Z",
                            "sourcecountry": "South Africa",
                        }
                    ]
                }
            )
        }
    )
    report = run_social_listening(
        tmp_path,
        adapters=[PublicWebAdapter(http=http, env={}, spec=_spec())],
        fixture_path=FIXTURE,
        write_outputs=False,
    )
    assert classify_source_class("LIVE") == "LIVE"
    assert classify_source_class("TEST_FIXTURE") == "FIXTURE"
    assert classify_source_class("MOCK") == "MOCK"
    assert classify_source_class(None) == "UNKNOWN"
    live_rows = [item for item in report.observations if classify_source_class(item.data_quality) == "LIVE"]
    fixture_rows = [item for item in report.observations if classify_source_class(item.data_quality) == "FIXTURE"]
    assert live_rows
    assert fixture_rows
    assert all(item.source_url.startswith("https://news.example/") for item in live_rows)
    assert all(item.source_url.startswith("https://example.test/") for item in fixture_rows)


def test_fixture_registry_has_record_count() -> None:
    result = FixtureAdapter(FIXTURE).collect()
    assert result.entry.record_count == len(result.posts)
    assert result.entry.error is None
    assert result.entry.status == "AVAILABLE"


def test_anonymisation_is_applied_for_live_authors(tmp_path: Path) -> None:
    http = FakeHttp(
        {
            ("POST", "access_token"): _json({"access_token": "tok"}),
            ("GET", "oauth.reddit.com/search"): _json(
                {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "permalink": "/r/test/comments/zz/post/",
                                    "title": "Unilever Sunlight review",
                                    "selftext": "works",
                                    "author": "visible_handle",
                                    "created_utc": 1754006400,
                                }
                            }
                        ]
                    }
                }
            ),
        }
    )
    report = run_social_listening(
        tmp_path,
        adapters=[
            RedditAdapter(http=http, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"}, spec=_spec())
        ],
        write_outputs=False,
    )
    blob = str(report.to_json_dict())
    assert "visible_handle" not in blob
    assert report.observations[0].author_id_hash
    assert report.observations[0].author_id_hash.startswith("anon_")
    assert report.observations[0].data_quality == "LIVE"


def test_english_is_not_treated_as_south_africa() -> None:
    http = FakeHttp(
        {
            ("GET", "gdeltproject.org"): _json(
                {
                    "articles": [
                        {
                            "url": "https://news.example/us",
                            "title": "Unilever English language article",
                            "seendate": "20260801T000000Z",
                            "language": "English",
                            "sourcecountry": "",
                        }
                    ]
                }
            )
        }
    )
    result = PublicWebAdapter(http=http, env={}, spec=_spec()).collect()
    assert result.posts[0].country is None
    assert result.posts[0].region is None
    assert result.posts[0].language == "English"


def test_reddit_geography_uses_subreddit_and_post_evidence_not_the_query() -> None:
    http = FakeHttp(
        {
            ("POST", "access_token"): _json({"access_token": "tok"}),
            ("GET", "oauth.reddit.com/search"): _json(
                {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "permalink": "/r/worldnews/comments/aa/unilever/",
                                    "subreddit": "worldnews",
                                    "title": "Unilever quarterly results",
                                    "selftext": "Global earnings call.",
                                    "author": "market_user",
                                    "created_utc": 1754006400,
                                }
                            },
                            {
                                "data": {
                                    "permalink": "/r/uk/comments/bb/tesco/",
                                    "subreddit": "uk",
                                    "title": "Unilever prices at Tesco",
                                    "selftext": "",
                                    "author": "shopper",
                                    "created_utc": 1754006400,
                                }
                            },
                            {
                                "data": {
                                    "permalink": "/r/gardening/comments/cc/shoprite/",
                                    "subreddit": "gardening",
                                    "title": "Sunlight dishwashing from Shoprite",
                                    "selftext": "",
                                    "author": "local",
                                    "created_utc": 1754006400,
                                }
                            },
                            {
                                "data": {
                                    "permalink": "/r/capetown/comments/dd/handy/",
                                    "subreddit": "capetown",
                                    "title": "Handy Andy restock",
                                    "selftext": "",
                                    "author": "ct_user",
                                    "created_utc": 1754006400,
                                }
                            },
                        ]
                    }
                }
            ),
        }
    )
    result = RedditAdapter(
        http=http, env={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"}, spec=_spec()
    ).collect()
    world = next(item for item in result.posts if "/r/worldnews/" in item.source_url)
    uk = next(item for item in result.posts if "/r/uk/" in item.source_url)
    shoprite = next(item for item in result.posts if "/r/gardening/" in item.source_url)
    cape = next(item for item in result.posts if "/r/capetown/" in item.source_url)
    assert world.country is None
    assert uk.country is None
    assert shoprite.country == "ZA"
    assert cape.country == "ZA"
    assert cape.region == "Cape Town"
