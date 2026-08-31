"""Causal-language guard. Social intelligence is not sales causality."""

from __future__ import annotations

from backend.agents.social_common.models import SocialConfig

DEFAULT_FORBIDDEN = (
    "will increase",
    "causes",
    "caused",
    "guaranteed incremental sales",
    "booked revenue",
    "proof that",
)


FORBIDDEN_ACTIONS = (
    "increase distribution",
    "cut the price",
    "launch a promotion",
    "raise coverage",
    "booked revenue",
)


def flatten_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(flatten_strings(item))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            out.extend(flatten_strings(item))
        return out
    return []


def assert_no_causal_language(texts: list[str], config: SocialConfig | None = None) -> None:
    forbidden = tuple(config.causality_forbidden) if config and config.causality_forbidden else DEFAULT_FORBIDDEN
    blob = " ".join(texts).lower()
    if "guaranteed incremental sales" in blob and "not guaranteed incremental sales" not in blob:
        raise ValueError("Social text claims guaranteed incremental sales")
    for phrase in forbidden:
        if phrase == "guaranteed incremental sales":
            continue
        if phrase in blob:
            raise ValueError(f"Unsupported causal language: {phrase}")


def assert_no_commercial_actions(texts: list[str]) -> None:
    blob = " ".join(texts).lower()
    for phrase in FORBIDDEN_ACTIONS:
        if phrase == "booked revenue" and "not booked revenue" in blob:
            continue
        if phrase in blob:
            raise ValueError(f"Social intelligence created a commercial action: {phrase}")


def assert_payload_safe(payload: object, config: SocialConfig | None = None) -> None:
    texts = flatten_strings(payload)
    assert_no_causal_language(texts, config)
    assert_no_commercial_actions(texts)
