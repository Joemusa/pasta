"""Source adapters. Credentials are required for live APIs; robots.txt is not bypassed."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agents.social_common.models import SourceRegistryEntry
from backend.agents.social_common.paths import SocialLoadError, read_json


@dataclass
class RawPost:
    source: str
    source_type: str
    source_url: str
    author: str | None
    published_at: str | None
    text: str
    language: str | None = None
    engagement: float | None = None
    region: str | None = None
    country: str | None = None
    data_quality: str = "LIVE"


@dataclass
class CollectionResult:
    entry: SourceRegistryEntry
    posts: list[RawPost] = field(default_factory=list)


class SourceAdapter:
    name = "base"
    source_type = "social"
    access_method = "none"

    def collect(self) -> CollectionResult:
        raise NotImplementedError


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _unavailable(name: str, source_type: str, method: str, reason: str) -> CollectionResult:
    return CollectionResult(
        entry=SourceRegistryEntry(
            source=name,
            source_type=source_type,
            access_method=method,
            status="UNAVAILABLE",
            last_successful_collection=None,
            limitations=[reason],
        )
    )


class RedditAdapter(SourceAdapter):
    name = "reddit"
    source_type = "social"
    access_method = "official_oauth_api"

    def collect(self) -> CollectionResult:
        if not os.environ.get("REDDIT_CLIENT_ID") or not os.environ.get("REDDIT_CLIENT_SECRET"):
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "OAuth credentials were not provided. Unauthenticated JSON is blocked (HTTP 403) "
                "and robots.txt disallows crawling (Disallow: /).",
            )
        return _unavailable(
            self.name,
            self.source_type,
            self.access_method,
            "Reddit OAuth collection is not enabled in V1 beyond credential detection.",
        )


class YouTubeAdapter(SourceAdapter):
    name = "youtube"
    source_type = "social"
    access_method = "official_data_api"

    def collect(self) -> CollectionResult:
        if not os.environ.get("YOUTUBE_API_KEY"):
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "YouTube Data API key was not provided. Unauthenticated search returns HTTP 403.",
            )
        return _unavailable(
            self.name,
            self.source_type,
            self.access_method,
            "YouTube Data API collection is not enabled in V1 beyond credential detection.",
        )


class XAdapter(SourceAdapter):
    name = "x"
    source_type = "social"
    access_method = "official_api"

    def collect(self) -> CollectionResult:
        if not os.environ.get("X_BEARER_TOKEN"):
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "X bearer token was not provided. Search API returns HTTP 401 without authentication.",
            )
        return _unavailable(
            self.name,
            self.source_type,
            self.access_method,
            "X API collection is not enabled in V1 beyond credential detection.",
        )


class FixtureAdapter(SourceAdapter):
    name = "test_fixtures"
    source_type = "test"
    access_method = "local_json_fixture"

    def __init__(self, path: Path) -> None:
        self.path = path

    def collect(self) -> CollectionResult:
        payload = read_json(self.path, kind="social fixture")
        if payload.get("data_mode") not in {"TEST_FIXTURES_ONLY", "test", "TEST"}:
            raise SocialLoadError(f"Fixture {self.path} is missing data_mode=TEST_FIXTURES_ONLY")
        posts: list[RawPost] = []
        for item in payload.get("posts") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("source_url") or "").strip()
            text = str(item.get("text") or item.get("text_or_excerpt") or "").strip()
            if not url or not text:
                continue
            posts.append(
                RawPost(
                    source=str(item.get("source") or "test_fixtures"),
                    source_type=str(item.get("source_type") or "test"),
                    source_url=url,
                    author=None if item.get("author") is None else str(item.get("author")),
                    published_at=None if item.get("published_at") in {None, ""} else str(item.get("published_at")),
                    text=text,
                    language=None if item.get("language") in {None, ""} else str(item.get("language")),
                    engagement=_num(item.get("engagement")),
                    region=None if item.get("region") in {None, ""} else str(item.get("region")),
                    country=None if item.get("country") in {None, ""} else str(item.get("country")),
                    data_quality="TEST_FIXTURE",
                )
            )
        status: str = "AVAILABLE" if posts else "INSUFFICIENT_EVIDENCE"
        return CollectionResult(
            entry=SourceRegistryEntry(
                source=self.name,
                source_type=self.source_type,
                access_method=self.access_method,
                status=status,  # type: ignore[arg-type]
                last_successful_collection=_now() if posts else None,
                limitations=[
                    "TEST FIXTURES ONLY. These posts are labeled test data and are not live social observations.",
                    f"Loaded {len(posts)} labeled fixture post(s) from {self.path}.",
                ],
            ),
            posts=posts,
        )


class PublicWebAdapter(SourceAdapter):
    name = "public_web"
    source_type = "web"
    access_method = "official_api_or_licensed_feed"

    def collect(self) -> CollectionResult:
        return _unavailable(
            self.name,
            self.source_type,
            self.access_method,
            "No officially accessible public-web discussion API is configured. "
            "The system does not crawl the public web or bypass robots.txt.",
        )


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def default_live_adapters() -> list[SourceAdapter]:
    return [RedditAdapter(), YouTubeAdapter(), XAdapter(), PublicWebAdapter()]
