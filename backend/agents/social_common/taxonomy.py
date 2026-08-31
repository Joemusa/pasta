"""Load expandable Unilever/FMCG taxonomy. Matching rules live in YAML, not agent if-blocks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from backend.agents.social_common.models import DEFAULT_TAXONOMY_PATH


def load_taxonomy(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_TAXONOMY_PATH
    payload = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Taxonomy {target} is not a mapping")
    return payload


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _hit(text: str, alias: str) -> bool:
    alias_n = _norm(alias)
    if not alias_n:
        return False
    if " " in alias_n:
        return alias_n in text
    return re.search(rf"\b{re.escape(alias_n)}\b", text) is not None


def _require(text: str, tokens: list[str] | None) -> bool:
    if not tokens:
        return True
    return any(_hit(text, token) for token in tokens)


def match_named(text: str, mapping: dict[str, Any]) -> str | None:
    blob = _norm(text)
    for name, spec in mapping.items():
        aliases = [name, *list(spec.get("aliases") or [])]
        if any(_hit(blob, alias) for alias in aliases) and _require(blob, spec.get("require_any")):
            return name
    return None


def match_topics(text: str, mapping: dict[str, Any]) -> list[str]:
    blob = _norm(text)
    found: list[str] = []
    for name, spec in mapping.items():
        aliases = [name.replace("_", " "), *list(spec.get("aliases") or [])]
        if any(_hit(blob, alias) for alias in aliases):
            found.append(name)
    return found


def match_needs(text: str, taxonomy: dict[str, Any]) -> list[str]:
    """Needs are YAML-driven. A need is returned only when aliases hit the text."""
    return match_topics(text, taxonomy.get("needs") or {})


def topic_spec(taxonomy: dict[str, Any], name: str) -> dict[str, Any]:
    topics = taxonomy.get("topics") or {}
    needs = taxonomy.get("needs") or {}
    spec = topics.get(name) or needs.get(name) or {}
    return spec if isinstance(spec, dict) else {}
