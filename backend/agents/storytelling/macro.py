"""Load and attach frozen macro context. Supporting background only; POS values are not rescored."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.agents.storytelling.loader import StorytellingLoadError, _display, _read_json
from backend.agents.storytelling.models import (
    MACRO_CAUSALITY_DISCLAIMER,
    MACRO_CONTEXT_VERSION,
    Confidence,
    MacroContextBlock,
    OneSlideStory,
)

MACRO_FILENAME = "macro_context_v1.json"


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"YES", "TRUE", "Y", "1"}


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _confidence(value: object) -> Confidence:
    label = _text(value).upper()
    if label not in {"HIGH", "MEDIUM", "LOW"}:
        raise StorytellingLoadError(f"Macro context confidence must be HIGH, MEDIUM, or LOW, not {value!r}")
    return label  # type: ignore[return-value]


def data_root_for(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_dir():
        return path
    if path.parent.name in {"brain_reports", "storytelling_reports", "macro_context"}:
        return path.parent.parent
    return path.parent


def discover_macro_pack(path: Path) -> tuple[dict[str, Any] | None, Path | None]:
    """Return the frozen pack if present. Missing is allowed; malformed is not."""
    named = data_root_for(path) / "macro_context" / MACRO_FILENAME
    if not named.is_file():
        return None, None
    payload = _read_json(named, kind="frozen macro context pack")
    return payload, named


def parse_macro_pack(payload: dict[str, Any], source: Path) -> MacroContextBlock:
    required = (
        "signal",
        "evidence",
        "direction",
        "relevance",
        "supports_pos_story",
        "commercial_implication",
        "confidence",
        "sources",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise StorytellingLoadError(f"Frozen macro pack is missing fields: {', '.join(missing)}")

    sources_raw = payload.get("sources")
    if isinstance(sources_raw, str):
        sources = [item.strip() for item in sources_raw.split(",") if item.strip()]
    elif isinstance(sources_raw, list):
        sources = [_text(item) for item in sources_raw if _text(item)]
    else:
        raise StorytellingLoadError("Frozen macro pack sources must be a list or comma-separated string")

    supports = _truthy(payload.get("supports_pos_story"))
    signal = _text(payload.get("signal"))
    evidence = _text(payload.get("evidence"))
    if not signal or not evidence:
        raise StorytellingLoadError("Frozen macro pack signal and evidence must be non-empty")

    supporting_line = ""
    role: str
    exclusion_reason: str | None
    if supports:
        role = "supporting_context"
        exclusion_reason = None
        supporting_line = f"Supporting context: {signal[0].lower() + signal[1:]} ({evidence})."
    else:
        role = "excluded"
        exclusion_reason = (
            "Frozen pack does not support the POS story; it is recorded but not shown as supporting evidence."
        )

    evidence_as_of = payload.get("evidence_as_of")
    if evidence_as_of is not None and _text(evidence_as_of) == "":
        evidence_as_of = None
    elif evidence_as_of is not None:
        evidence_as_of = _text(evidence_as_of)

    return MacroContextBlock(
        included=supports,
        role=role,  # type: ignore[arg-type]
        version=_text(payload.get("version")) or MACRO_CONTEXT_VERSION,
        signal=signal,
        evidence=evidence,
        direction=_text(payload.get("direction")).upper() or None,
        relevance=_text(payload.get("relevance")).upper() or None,
        supports_pos_story=supports,
        commercial_implication=_text(payload.get("commercial_implication")) or None,
        confidence=_confidence(payload.get("confidence")),
        sources=sources,
        supporting_line=supporting_line,
        causality_disclaimer=_text(payload.get("causality_disclaimer")) or MACRO_CAUSALITY_DISCLAIMER,
        evidence_as_of=evidence_as_of,
        source_path=_display(source),
        exclusion_reason=exclusion_reason,
    )


def attach_macro_context(story: OneSlideStory, block: MacroContextBlock) -> OneSlideStory:
    """Copy the POS story and attach macro as supporting context. Headline and values stay put."""
    return story.model_copy(update={"macro_context": block})
