"""Polite HTTP for official APIs. Does not bypass robots.txt, auth, or rate limits."""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 20


@dataclass
class HttpResponse:
    status_code: int
    body: str
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""

    def json(self) -> Any:
        if not self.body.strip():
            return None
        return json.loads(self.body)


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class HttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: int = DEFAULT_TIMEOUT,
        min_interval_seconds: float = 1.0,
        opener=None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval_seconds = min_interval_seconds
        self._opener = opener
        self._last_request_at = 0.0

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        return self.request("GET", url, headers=headers)

    def post(self, url: str, data: bytes, *, headers: dict[str, str] | None = None) -> HttpResponse:
        return self.request("POST", url, data=data, headers=headers)

    def request(
        self, method: str, url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None
    ) -> HttpResponse:
        self._pace()
        merged = {"User-Agent": self.user_agent, "Accept": "application/json, application/xml, text/xml, */*"}
        if headers:
            merged.update(headers)
        request = Request(url, data=data, headers=merged, method=method)
        previous_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(self.timeout)
            if self._opener is not None:
                raw = self._opener(request, timeout=self.timeout)
                status, body, hdrs, final_url = raw
                return HttpResponse(status_code=int(status), body=str(body), headers=dict(hdrs), url=str(final_url))
            with urlopen(request, timeout=self.timeout) as resp:
                payload = resp.read().decode("utf-8", "replace")
                hdrs = {str(k).lower(): str(v) for k, v in resp.headers.items()}
                return HttpResponse(status_code=int(resp.status), body=payload, headers=hdrs, url=str(resp.geturl()))
        except HTTPError as exc:
            payload = exc.read().decode("utf-8", "replace") if exc.fp else ""
            retryable = exc.code in {429, 500, 502, 503, 504}
            if exc.code == 429:
                raise HttpError("rate_limited", status_code=429, retryable=True) from exc
            raise HttpError(f"http_{exc.code}", status_code=exc.code, retryable=retryable) from exc
        except URLError as exc:
            raise HttpError(f"network_error:{exc.reason}", retryable=True) from exc
        except TimeoutError as exc:
            raise HttpError("timeout", retryable=True) from exc
        except OSError as exc:
            raise HttpError(f"network_error:{exc}", retryable=True) from exc
        finally:
            socket.setdefaulttimeout(previous_timeout)

    def _pace(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()
