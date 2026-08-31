"""Align social timestamps to the POS window. Future posts do not explain POS."""

from __future__ import annotations

from datetime import date, datetime

from backend.agents.social_common.models import SocialConfig


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_iso_date(value: str | None) -> date | None:
    stamp = parse_timestamp(value)
    return None if stamp is None else stamp.date()


def align_published(published_at: str | None, config: SocialConfig) -> tuple[str, str]:
    observed = parse_iso_date(published_at)
    pos_end = parse_iso_date(config.pos_period_end)
    pos_start = parse_iso_date(config.pos_period_start)
    if observed is None:
        return "published_at_not_supplied", "INSUFFICIENT_DATES"
    if pos_end is None or pos_start is None:
        return "pos_window_missing", "INSUFFICIENT_DATES"
    if observed > pos_end:
        return "published_after_pos_period_end", "FUTURE_LEAKAGE"
    return "published_on_or_before_pos_period_end", "ALIGNED"


def pos_aligned(observations: list, config: SocialConfig | None = None) -> list:
    """Observations that may be compared with historical POS. Future posts are excluded."""
    del config
    return [item for item in observations if getattr(item, "alignment_status", None) == "ALIGNED"]


def non_future(observations: list) -> list:
    return [item for item in observations if getattr(item, "alignment_status", None) != "FUTURE_LEAKAGE"]


def split_recent_baseline(observations: list, config: SocialConfig) -> tuple[list, list]:
    start = parse_iso_date(config.pos_period_start)
    end = parse_iso_date(config.pos_period_end)
    if start is None or end is None:
        return [], []
    mid = start + (end - start) / 2
    recent: list = []
    baseline: list = []
    for item in observations:
        observed = parse_iso_date(getattr(item, "published_at", None))
        if observed is None or observed > end:
            continue
        if observed > mid:
            recent.append(item)
        else:
            baseline.append(item)
    return recent, baseline
