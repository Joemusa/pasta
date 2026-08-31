"""Causal-language guard for macro implications. Macro does not explain POS gaps."""

from __future__ import annotations

from backend.agents.macro_common.models import MacroConfig

DEFAULT_FORBIDDEN = (
    "will increase",
    "causes",
    "caused",
    "guaranteed incremental sales",
    "booked revenue",
)


def assert_no_causal_language(texts: list[str], config: MacroConfig | None = None) -> None:
    forbidden = tuple(config.causality_forbidden) if config and config.causality_forbidden else DEFAULT_FORBIDDEN
    blob = " ".join(texts).lower()
    if "guaranteed incremental sales" in blob and "not guaranteed incremental sales" not in blob:
        raise ValueError("Macro text claims guaranteed incremental sales")
    for phrase in forbidden:
        if phrase == "guaranteed incremental sales":
            continue
        if phrase in blob:
            raise ValueError(f"Unsupported causal language: {phrase}")
