"""Path helpers for social reports. Frozen POS/macro folders are not written."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SocialLoadError(ValueError):
    """Social intelligence inputs cannot be used."""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def data_root_for(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_dir():
        if path.name in {
            "social_reports",
            "social_fixture_reports",
            "brain_reports",
            "macro_context",
        }:
            return path.parent
        return path
    if path.parent.name in {
        "social_reports",
        "social_fixture_reports",
        "brain_reports",
        "tests",
        "fixtures",
        "social",
    }:
        if path.parent.name == "social" and path.parent.parent.name == "fixtures":
            return path.parents[3] if len(path.parents) >= 4 else path.parent
        return path.parent.parent
    return path.parent


def read_json(path: Path, *, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SocialLoadError(f"Cannot read {kind} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SocialLoadError(f"{path} is not a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
