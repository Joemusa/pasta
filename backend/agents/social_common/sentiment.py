"""Deterministic lexicon sentiment. Missing evidence stays missing; posts are never invented."""

from __future__ import annotations

from collections import Counter

from backend.agents.social_common.models import Intensity, SentimentBreakdown, SentimentLabel, SocialObservation
from backend.agents.social_common.taxonomy import _hit, _norm


def classify_text(text: str, lexicon: dict) -> tuple[SentimentLabel, Intensity]:
    blob = _norm(text)
    pos_hits = [word for word in lexicon.get("positive") or [] if _hit(blob, word)]
    neg_hits = [word for word in lexicon.get("negative") or [] if _hit(blob, word)]
    if pos_hits and neg_hits:
        label: SentimentLabel = "MIXED"
    elif pos_hits:
        label = "POSITIVE"
    elif neg_hits:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"
    hits = pos_hits + neg_hits
    high = [word for word in lexicon.get("high_intensity") or [] if _hit(blob, word)]
    medium = [word for word in lexicon.get("medium_intensity") or [] if _hit(blob, word)]
    intensity: Intensity = "LOW"
    if high or len(hits) >= 3:
        intensity = "HIGH"
    elif medium or len(hits) == 2:
        intensity = "MEDIUM"
    elif hits:
        intensity = "LOW"
    return label, intensity


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def breakdown(labels: list[SentimentLabel]) -> SentimentBreakdown:
    n = len(labels)
    counts = Counter(labels)
    pos = counts.get("POSITIVE", 0)
    neg = counts.get("NEGATIVE", 0)
    neu = counts.get("NEUTRAL", 0)
    mix = counts.get("MIXED", 0)
    if pos > neg and pos >= neu:
        overall: SentimentLabel = "POSITIVE"
    elif neg > pos and neg >= neu:
        overall = "NEGATIVE"
    elif mix and mix >= max(pos, neg, neu):
        overall = "MIXED"
    elif n == 0:
        overall = "NEUTRAL"
    else:
        overall = "NEUTRAL" if neu >= max(pos, neg, mix) else "MIXED"
    intensity: Intensity = "LOW"
    if n >= 20:
        intensity = "HIGH"
    elif n >= 8:
        intensity = "MEDIUM"
    return SentimentBreakdown(
        label=overall,
        intensity=intensity,
        share_positive=ratio(pos, n),
        share_negative=ratio(neg, n),
        share_neutral=ratio(neu, n),
        share_mixed=ratio(mix, n),
        positive_negative_ratio=None if neg == 0 else ratio(pos, neg),
        evidence_count=n,
    )


def slice_sentiment(
    observations: list[SocialObservation], lexicon: dict, topic: str | None = None
) -> SentimentBreakdown:
    rows = observations if topic is None else [item for item in observations if topic in item.topics]
    labels = [classify_text(item.text_or_excerpt, lexicon)[0] for item in rows]
    result = breakdown(labels)
    if topic is not None and not rows:
        return SentimentBreakdown(
            label="NEUTRAL",
            intensity="LOW",
            share_positive=None,
            share_negative=None,
            share_neutral=None,
            share_mixed=None,
            positive_negative_ratio=None,
            evidence_count=0,
        )
    return result


def slice_where(observations: list[SocialObservation], predicate) -> list[SocialObservation]:
    return [item for item in observations if predicate(item)]


def dimension_slices(observations: list[SocialObservation]) -> dict[str, list[SocialObservation]]:
    return {
        "product": [item for item in observations if item.product],
        "brand": [item for item in observations if item.brand],
        "price": [item for item in observations if "price" in item.topics],
        "promotion": [item for item in observations if "promotion" in item.topics],
        "availability": [item for item in observations if "availability" in item.topics],
        "service": [item for item in observations if "retailer" in item.topics],
    }


def dimension_breakdowns(
    observations: list[SocialObservation],
    lexicon: dict,
) -> dict[str, SentimentBreakdown]:
    out: dict[str, SentimentBreakdown] = {}
    for name, rows in dimension_slices(observations).items():
        if not rows:
            out[name] = SentimentBreakdown(
                label="NEUTRAL",
                intensity="LOW",
                share_positive=None,
                share_negative=None,
                share_neutral=None,
                share_mixed=None,
                positive_negative_ratio=None,
                evidence_count=0,
            )
        else:
            out[name] = breakdown([classify_text(item.text_or_excerpt, lexicon)[0] for item in rows])
    return out


def majority_sentiment(labels: list[SentimentLabel]) -> SentimentLabel:
    if not labels:
        return "NEUTRAL"
    return breakdown(labels).label
