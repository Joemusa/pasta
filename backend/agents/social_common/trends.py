"""Trend labels. A trend is not claimed without enough history."""

from __future__ import annotations

from backend.agents.social_common.models import SocialConfig, TrendLabel


def classify_trend(recent_count: int, baseline_count: int, config: SocialConfig) -> TrendLabel:
    total = recent_count + baseline_count
    if total < config.trend_min_total or recent_count < config.trend_min_recent:
        return "INSUFFICIENT_EVIDENCE"
    if baseline_count == 0:
        return "EMERGING"
    ratio = recent_count / baseline_count
    if ratio >= config.trend_growth_ratio:
        return "GROWING"
    if recent_count * config.trend_growth_ratio <= baseline_count:
        return "DECLINING"
    return "STABLE"
