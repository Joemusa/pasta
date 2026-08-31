"""Confidence from observation count, source diversity, consistency and recency. Never HIGH from one post."""

from __future__ import annotations

from backend.agents.social_common.models import Confidence, SocialConfig, SocialObservation


def insight_confidence(
    observations: list[SocialObservation],
    config: SocialConfig,
    *,
    consistent: bool = True,
) -> Confidence:
    n = len(observations)
    sources = {item.source for item in observations if item.source}
    if n == 0:
        return "LOW"
    if n < config.never_high_below_observations:
        return "LOW"
    if (
        consistent
        and n >= config.high_min_observations
        and len(sources) >= config.high_min_sources
    ):
        return "HIGH"
    if n >= config.medium_min_observations and len(sources) >= config.medium_min_sources:
        return "MEDIUM"
    if n >= config.medium_min_observations:
        return "MEDIUM"
    return "LOW"
