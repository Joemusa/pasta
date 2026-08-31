"""Author anonymisation. Raw author identifiers are not persisted."""

from __future__ import annotations

import hashlib


def hash_author(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"anonymous", "deleted", "[deleted]", "unknown"}:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"anon_{digest[:16]}"


def content_fingerprint(source_url: str, excerpt: str) -> str:
    blob = f"{source_url.strip().casefold()}|{excerpt.strip().casefold()}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
