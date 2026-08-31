"""Source adapters. Official APIs and permitted public endpoints only; robots.txt is not bypassed."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from backend.agents.social_common.http_client import HttpClient, HttpError, HttpResponse
from backend.agents.social_common.models import SourceRegistryEntry
from backend.agents.social_common.paths import SocialLoadError, read_json
from backend.agents.social_common.queries import expand_search_queries, load_query_spec, user_agent
from backend.agents.social_common.taxonomy import load_taxonomy

LIVE = "LIVE"
FIXTURE = "FIXTURE"
MOCK = "MOCK"
UNKNOWN = "UNKNOWN"
DELETED_MARKERS = frozenset({"[deleted]", "[removed]", "deleted", "removed"})


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
    data_quality: str = LIVE


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


def classify_source_class(data_quality: str | None) -> str:
    value = (data_quality or "").strip().upper()
    if value in {LIVE, "LIVE_SOCIAL"}:
        return LIVE
    if value in {FIXTURE, "TEST_FIXTURE", "TEST_FIXTURES_ONLY", "TEST"}:
        return FIXTURE
    if value == MOCK:
        return MOCK
    return UNKNOWN


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_deleted(text: str, author: str | None = None) -> bool:
    blob = text.strip().casefold()
    if blob in DELETED_MARKERS or not blob:
        return True
    if author and str(author).strip().casefold() in DELETED_MARKERS:
        return True
    return False


def _dedupe_posts(posts: list[RawPost]) -> list[RawPost]:
    seen: set[str] = set()
    unique: list[RawPost] = []
    for item in posts:
        key = item.source_url.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _status(posts: list[RawPost], errors: list[str], queries_attempted: int) -> str:
    if errors and posts:
        return "PARTIAL"
    if errors and not posts:
        return "UNAVAILABLE"
    if queries_attempted == 0 and not posts:
        return "UNAVAILABLE"
    return "AVAILABLE"


def _entry(
    *,
    source: str,
    source_type: str,
    access_method: str,
    status: str,
    posts: list[RawPost],
    errors: list[str],
    limitations: list[str],
) -> SourceRegistryEntry:
    return SourceRegistryEntry(
        source=source,
        source_type=source_type,
        access_method=access_method,
        status=status,  # type: ignore[arg-type]
        last_successful_collection=_now() if posts else None,
        record_count=len(posts),
        error=errors[0] if errors else None,
        limitations=limitations,
    )


def _unavailable(name: str, source_type: str, method: str, reason: str) -> CollectionResult:
    return CollectionResult(
        entry=_entry(
            source=name,
            source_type=source_type,
            access_method=method,
            status="UNAVAILABLE",
            posts=[],
            errors=[reason],
            limitations=[reason],
        )
    )


def _live_network_enabled(env: dict[str, str] | None) -> bool:
    merged = {**os.environ, **(env or {})}
    flag = (merged.get("SOCIAL_LIVE_NETWORK") or "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    if flag in {"1", "true", "yes", "on"}:
        return True
    return not bool(merged.get("PYTEST_CURRENT_TEST"))


def _client(spec: dict[str, Any], http: Any) -> Any:
    if http is not None:
        return http
    return HttpClient(
        user_agent=user_agent(spec),
        timeout=int(spec.get("request_timeout_seconds") or 20),
        min_interval_seconds=float(spec.get("rate_limit_sleep_seconds") or 1.0),
    )


def _map_country(raw: str | None, spec: dict[str, Any]) -> str | None:
    if not raw:
        return None
    mapping = spec.get("country_iso") or {}
    mapped = mapping.get(raw.strip().casefold())
    if mapped:
        return str(mapped)
    return raw.strip() or None


def _iso_from_gdelt(value: str) -> str | None:
    if len(value) >= 15 and value[8] == "T":
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}T{value[9:11]}:{value[11:13]}:{value[13:15]}Z"
    return None


class RedditAdapter(SourceAdapter):
    name = "reddit"
    source_type = "social"
    access_method = "official_oauth_api"

    def __init__(
        self, *, http: Any = None, env: dict[str, str] | None = None, spec: dict | None = None
    ) -> None:
        self.env = env if env is not None else dict(os.environ)
        self.spec = spec if spec is not None else load_query_spec()
        self._injected_http = http is not None
        self.http = _client(self.spec, http)

    def collect(self) -> CollectionResult:
        cfg = self.spec.get("reddit") or {}
        client_id = (self.env.get(str(cfg.get("env_client_id") or "REDDIT_CLIENT_ID")) or "").strip()
        secret = (self.env.get(str(cfg.get("env_client_secret") or "REDDIT_CLIENT_SECRET")) or "").strip()
        if not client_id or not secret:
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "OAuth credentials were not provided. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET. "
                "Unauthenticated JSON is blocked (HTTP 403) and robots.txt disallows crawling (Disallow: /).",
            )
        if not self._injected_http and not _live_network_enabled(self.env):
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "Live Reddit HTTP is disabled in this process. Set SOCIAL_LIVE_NETWORK=1 to collect.",
            )
        try:
            token = self._token(client_id, secret, str(cfg.get("token_url")))
        except HttpError as exc:
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                f"Reddit token request failed ({exc}). Official OAuth is required.",
            )
        queries = expand_search_queries(self.spec, load_taxonomy(), source="reddit")
        posts: list[RawPost] = []
        errors: list[str] = []
        limit = int(self.spec.get("max_results_per_query") or 8)
        search_url = str(cfg.get("search_url") or "https://oauth.reddit.com/search")
        headers = {"Authorization": f"Bearer {token}"}
        for query in queries:
            try:
                params = {"q": query.text, "limit": str(limit), "sort": "new", "t": "month", "raw_json": "1"}
                posts.extend(self._parse_listing(self.http.get(f"{search_url}?{urlencode(params)}", headers=headers)))
            except HttpError as exc:
                errors.append(f"{query.query_id}:{exc}")
                if exc.status_code == 429:
                    break
        posts = _dedupe_posts(posts)
        notes = [
            "Reddit official OAuth application-only search. HTML crawling is not used.",
            "Author identifiers are passed through for hashing and are not stored as display names.",
            "Country/region stay null unless Reddit supplies geography (language is not used as a proxy).",
        ]
        if errors:
            notes.append("Some Reddit queries failed: " + "; ".join(errors[:4]))
        return CollectionResult(
            entry=_entry(
                source=self.name,
                source_type=self.source_type,
                access_method=self.access_method,
                status=_status(posts, errors, len(queries)),
                posts=posts,
                errors=errors,
                limitations=notes,
            ),
            posts=posts,
        )

    def _token(self, client_id: str, client_secret: str, token_url: str) -> str:
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
        body = urlencode({"grant_type": "client_credentials"}).encode()
        response = self.http.post(
            token_url,
            body,
            headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        )
        payload = response.json() or {}
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise HttpError("reddit_token_missing", status_code=response.status_code)
        return str(token)

    def _parse_listing(self, response: HttpResponse) -> list[RawPost]:
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        posts: list[RawPost] = []
        for child in data.get("children") or []:
            row = child.get("data") if isinstance(child, dict) else None
            if not isinstance(row, dict):
                continue
            permalink = str(row.get("permalink") or "").strip()
            url = (
                f"https://www.reddit.com{permalink}"
                if permalink.startswith("/")
                else str(row.get("url") or "").strip()
            )
            text = f"{_clean_text(row.get('title'))} {_clean_text(row.get('selftext'))}".strip()
            author_s = None if row.get("author") in {None, ""} else str(row.get("author"))
            if not url or _is_deleted(text, author_s):
                continue
            published = None
            if row.get("created_utc") not in {None, ""}:
                try:
                    published = (
                        datetime.fromtimestamp(float(row["created_utc"]), tz=UTC)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                except (TypeError, ValueError, OSError, KeyError):
                    published = None
            posts.append(
                RawPost(
                    source=self.name,
                    source_type=self.source_type,
                    source_url=url,
                    author=author_s,
                    published_at=published,
                    text=text,
                    engagement=_num(row.get("score")),
                    data_quality=LIVE,
                )
            )
        return posts


class YouTubeAdapter(SourceAdapter):
    name = "youtube"
    source_type = "social"
    access_method = "official_data_api"

    def __init__(
        self, *, http: Any = None, env: dict[str, str] | None = None, spec: dict | None = None
    ) -> None:
        self.env = env if env is not None else dict(os.environ)
        self.spec = spec if spec is not None else load_query_spec()
        self._injected_http = http is not None
        self.http = _client(self.spec, http)

    def collect(self) -> CollectionResult:
        cfg = self.spec.get("youtube") or {}
        key = (self.env.get(str(cfg.get("env_key") or "YOUTUBE_API_KEY")) or "").strip()
        if not key:
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "YouTube Data API key was not provided. Set YOUTUBE_API_KEY. "
                "Unauthenticated search returns HTTP 403. youtube.com HTML is not crawled.",
            )
        if not self._injected_http and not _live_network_enabled(self.env):
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "Live YouTube HTTP is disabled in this process. Set SOCIAL_LIVE_NETWORK=1 to collect.",
            )
        queries = expand_search_queries(self.spec, load_taxonomy(), source="youtube")
        posts: list[RawPost] = []
        errors: list[str] = []
        search_url = str(cfg.get("search_url") or "https://www.googleapis.com/youtube/v3/search")
        comments_url = str(cfg.get("comments_url") or "https://www.googleapis.com/youtube/v3/commentThreads")
        limit = int(self.spec.get("max_results_per_query") or 8)
        comment_limit = int(self.spec.get("max_youtube_comment_threads") or 5)
        region = str((self.spec.get("south_africa") or {}).get("youtube_region_code") or "").strip()
        video_ids: list[str] = []
        for query in queries:
            params = {
                "part": "snippet",
                "type": "video",
                "maxResults": str(min(limit, 10)),
                "q": query.text,
                "key": key,
            }
            if region:
                params["regionCode"] = region
            try:
                parsed, ids = self._parse_search(self.http.get(f"{search_url}?{urlencode(params)}"))
                posts.extend(parsed)
                video_ids.extend(ids)
            except HttpError as exc:
                errors.append(f"{query.query_id}:{exc}")
                if exc.status_code in {403, 429}:
                    break
        for video_id in list(dict.fromkeys(video_ids))[:comment_limit]:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": str(comment_limit),
                "textFormat": "plainText",
                "key": key,
            }
            try:
                posts.extend(self._parse_comments(self.http.get(f"{comments_url}?{urlencode(params)}"), video_id))
            except HttpError as exc:
                errors.append(f"comments:{video_id}:{exc}")
                if exc.status_code == 429:
                    break
        posts = _dedupe_posts(posts)
        notes = [
            "YouTube Data API v3 search and commentThreads only. youtube.com HTML is not crawled.",
            "regionCode=ZA is a search preference. Observation country stays null unless the API supplies geography.",
            "Author display names are passed for hashing only.",
        ]
        if errors:
            notes.append("Some YouTube requests failed: " + "; ".join(errors[:4]))
        return CollectionResult(
            entry=_entry(
                source=self.name,
                source_type=self.source_type,
                access_method=self.access_method,
                status=_status(posts, errors, len(queries)),
                posts=posts,
                errors=errors,
                limitations=notes,
            ),
            posts=posts,
        )

    def _parse_search(self, response: HttpResponse) -> tuple[list[RawPost], list[str]]:
        payload = response.json()
        if not isinstance(payload, dict):
            return [], []
        posts: list[RawPost] = []
        ids: list[str] = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            identity = item.get("id") if isinstance(item.get("id"), dict) else {}
            video_id = str(identity.get("videoId") or "").strip()
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            text = f"{_clean_text(snippet.get('title'))} {_clean_text(snippet.get('description'))}".strip()
            url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
            if not url or _is_deleted(text):
                continue
            ids.append(video_id)
            channel = snippet.get("channelTitle")
            posts.append(
                RawPost(
                    source=self.name,
                    source_type=self.source_type,
                    source_url=url,
                    author=None if channel in {None, ""} else str(channel),
                    published_at=None if not snippet.get("publishedAt") else str(snippet.get("publishedAt")),
                    text=text,
                    data_quality=LIVE,
                )
            )
        return posts, ids

    def _parse_comments(self, response: HttpResponse, video_id: str) -> list[RawPost]:
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        posts: list[RawPost] = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            wrapper = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            top = wrapper.get("topLevelComment") if isinstance(wrapper, dict) else {}
            snippet = top.get("snippet") if isinstance(top, dict) else {}
            if not isinstance(snippet, dict):
                continue
            text = _clean_text(snippet.get("textDisplay") or snippet.get("textOriginal"))
            comment_id = str(item.get("id") or "").strip()
            url = (
                f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"
                if comment_id
                else f"https://www.youtube.com/watch?v={video_id}"
            )
            author_s = None if snippet.get("authorDisplayName") in {None, ""} else str(snippet.get("authorDisplayName"))
            if _is_deleted(text, author_s):
                continue
            posts.append(
                RawPost(
                    source=self.name,
                    source_type="social_comment",
                    source_url=url,
                    author=author_s,
                    published_at=None if not snippet.get("publishedAt") else str(snippet.get("publishedAt")),
                    text=text,
                    engagement=_num(snippet.get("likeCount")),
                    data_quality=LIVE,
                )
            )
        return posts


class XAdapter(SourceAdapter):
    name = "x"
    source_type = "social"
    access_method = "official_api"

    def __init__(self, *, env: dict[str, str] | None = None) -> None:
        self.env = env if env is not None else dict(os.environ)

    def collect(self) -> CollectionResult:
        if not (self.env.get("X_BEARER_TOKEN") or "").strip():
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "X bearer token was not provided. Set X_BEARER_TOKEN. "
                "Search API returns HTTP 401 without authentication. "
                "X live collection is out of scope for this sprint.",
            )
        return _unavailable(
            self.name,
            self.source_type,
            self.access_method,
            "X API collection is not enabled in this sprint beyond credential detection. "
            "Set X_BEARER_TOKEN for a later adapter.",
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
        posts = _dedupe_posts(posts)
        status = "AVAILABLE" if posts else "INSUFFICIENT_EVIDENCE"
        return CollectionResult(
            entry=_entry(
                source=self.name,
                source_type=self.source_type,
                access_method=self.access_method,
                status=status,
                posts=posts,
                errors=[],
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
    access_method = "gdelt_doc_2_0_api"

    def __init__(
        self, *, http: Any = None, env: dict[str, str] | None = None, spec: dict | None = None
    ) -> None:
        self.env = env if env is not None else dict(os.environ)
        self.spec = spec if spec is not None else load_query_spec()
        self._injected_http = http is not None
        self.http = _client(self.spec, http)

    def collect(self) -> CollectionResult:
        if not self._injected_http and not _live_network_enabled(self.env):
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "Live public-web HTTP is disabled in this process. Set SOCIAL_LIVE_NETWORK=1 to collect "
                "from GDELT DOC 2.0 / NewsAPI.",
            )
        web = self.spec.get("public_web") or {}
        posts: list[RawPost] = []
        errors: list[str] = []
        attempted = 0
        methods = ["gdelt_doc_2_0_api"]
        gdelt_cfg = web.get("gdelt") or {}
        if gdelt_cfg.get("enabled", True):
            attempted += 1
            try:
                posts.extend(self._gdelt(gdelt_cfg))
            except HttpError as exc:
                errors.append(f"gdelt:{exc}")
        news_cfg = web.get("newsapi") or {}
        news_key = (self.env.get(str(news_cfg.get("env_key") or "NEWS_API_KEY")) or "").strip()
        if news_cfg.get("enabled", True) and news_key:
            methods.append("newsapi_v2")
            attempted += 1
            try:
                posts.extend(self._newsapi(news_cfg, news_key))
            except HttpError as exc:
                errors.append(f"newsapi:{exc}")
        posts = _dedupe_posts(posts)
        if attempted == 0:
            return _unavailable(
                self.name,
                self.source_type,
                self.access_method,
                "No public web/news API is enabled in social_queries.yaml. HTML crawling is not performed.",
            )
        status = _status(posts, errors, attempted)
        notes = [
            "Public web/news uses GDELT DOC 2.0 (public query API) and optional official NewsAPI. "
            "Google News HTML/RSS is not fetched because robots.txt disallows /rss.",
            "Article bodies are not scraped. Title/description plus source URL and publication date are retained.",
            "Country is set only when the source supplies geography. English language is not treated as South Africa.",
        ]
        if not news_key:
            notes.append("NewsAPI UNAVAILABLE until NEWS_API_KEY is configured.")
        if errors:
            notes.append("Public web errors: " + "; ".join(errors[:4]))
        if not posts and status == "AVAILABLE":
            notes.append("APIs responded but returned no matching articles.")
        return CollectionResult(
            entry=_entry(
                source=self.name,
                source_type=self.source_type,
                access_method="+".join(methods),
                status=status,
                posts=posts,
                errors=errors,
                limitations=notes,
            ),
            posts=posts,
        )

    def _gdelt(self, cfg: dict[str, Any]) -> list[RawPost]:
        endpoint = str(cfg.get("endpoint") or "https://api.gdeltproject.org/api/v2/doc/doc")
        queries = expand_search_queries(self.spec, load_taxonomy(), source="public_web")
        limit = int(self.spec.get("max_results_per_query") or 8)
        posts: list[RawPost] = []
        last_error: HttpError | None = None
        for query in queries:
            params = {
                "query": query.text,
                "mode": "ArtList",
                "maxrecords": str(min(limit, 50)),
                "format": str(cfg.get("format") or "json"),
                "timespan": str(cfg.get("timespan") or "3m"),
            }
            try:
                posts.extend(self._parse_gdelt(self.http.get(f"{endpoint}?{urlencode(params)}")))
            except HttpError as exc:
                last_error = exc
                if exc.status_code == 429 or exc.retryable:
                    if posts:
                        break
                    raise
                continue
        if not posts and last_error is not None:
            raise last_error
        return posts

    def _parse_gdelt(self, response: HttpResponse) -> list[RawPost]:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise HttpError("gdelt_invalid_json") from exc
        if payload is None:
            return []
        if isinstance(payload, list):
            articles = payload
        elif isinstance(payload, dict):
            articles = payload.get("articles") or []
        else:
            articles = []
        posts: list[RawPost] = []
        for item in articles:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = _clean_text(item.get("title"))
            if not url or _is_deleted(title):
                continue
            seen = str(item.get("seendate") or "").strip()
            posts.append(
                RawPost(
                    source=self.name,
                    source_type="news",
                    source_url=url,
                    author=None,
                    published_at=_iso_from_gdelt(seen) if seen else None,
                    text=title,
                    language=None if not item.get("language") else str(item.get("language")),
                    country=_map_country(
                        None if not item.get("sourcecountry") else str(item.get("sourcecountry")),
                        self.spec,
                    ),
                    data_quality=LIVE,
                )
            )
        return posts

    def _newsapi(self, cfg: dict[str, Any], api_key: str) -> list[RawPost]:
        endpoint = str(cfg.get("endpoint") or "https://newsapi.org/v2/everything")
        queries = expand_search_queries(self.spec, load_taxonomy(), source="public_web")
        limit = int(self.spec.get("max_results_per_query") or 8)
        posts: list[RawPost] = []
        for query in queries:
            text = query.text.replace("sourcecountry:SouthAfrica", "South Africa")
            params = {"q": text, "pageSize": str(min(limit, 20)), "sortBy": "publishedAt", "apiKey": api_key}
            payload = self.http.get(f"{endpoint}?{urlencode(params)}").json()
            if not isinstance(payload, dict):
                continue
            if payload.get("status") == "error":
                raise HttpError(str(payload.get("code") or payload.get("message") or "newsapi_error"))
            for item in payload.get("articles") or []:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                text_body = f"{_clean_text(item.get('title'))} {_clean_text(item.get('description'))}".strip()
                if not url or _is_deleted(text_body):
                    continue
                author = item.get("author")
                posts.append(
                    RawPost(
                        source=self.name,
                        source_type="news",
                        source_url=url,
                        author=None if author in {None, ""} else str(author),
                        published_at=None if not item.get("publishedAt") else str(item.get("publishedAt")),
                        text=text_body,
                        data_quality=LIVE,
                    )
                )
        return posts


def default_live_adapters() -> list[SourceAdapter]:
    return [RedditAdapter(), YouTubeAdapter(), XAdapter(), PublicWebAdapter()]
