"""Load Commercial Brain one-slide JSON. Specialist reports are not read."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("backend.agents.storytelling.loader")


class StorytellingLoadError(ValueError):
    """Storytelling Engine inputs cannot be used."""


def _display(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def refuse_raw(path: Path) -> None:
    parts = {part.lower() for part in path.expanduser().resolve().parts}
    name = path.name.lower()
    if "raw" in parts and "data" in parts and "integrated" not in parts:
        raise StorytellingLoadError("Storytelling Engine V1 does not read data/raw/ source files")
    if name.endswith(".clean.csv"):
        raise StorytellingLoadError("Storytelling Engine V1 does not read Data QA *.clean.csv files")
    if name.endswith(".commercial.csv"):
        raise StorytellingLoadError("Storytelling Engine V1 consumes Commercial Brain JSON only")


def _is_one_slide(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("top_actions"), list) and (
        "headline" in payload or "total_addressable_value_opportunity" in payload or "report_title" in payload
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorytellingLoadError(f"Cannot read Commercial Brain slide {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StorytellingLoadError(f"{path} is not a JSON object")
    return payload


def extract_one_slide(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("one_slide"), dict):
        slide = dict(payload["one_slide"])
        if not slide.get("limitations") and isinstance(payload.get("limitations"), list):
            slide["limitations"] = payload["limitations"]
        return slide
    if _is_one_slide(payload):
        return payload
    raise StorytellingLoadError("JSON is not a Commercial Brain one-slide or *.brain.json report")


def discover_brain_slide(path: Path) -> tuple[dict[str, Any], Path]:
    path = path.expanduser().resolve()
    refuse_raw(path)
    if path.is_file():
        payload = _read_json(path)
        return extract_one_slide(payload), path

    candidates: list[Path] = []
    named = [
        path / "commercial_brain_v1_one_slide.json",
        path / "storytelling_reports" / "commercial_brain_v1_one_slide.json",
        path / "brain_reports" / "commercial_brain_v1_one_slide.json",
    ]
    for item in named:
        if item.is_file():
            candidates.append(item)
    brain_dir = path / "brain_reports"
    if brain_dir.is_dir():
        candidates.extend(sorted(brain_dir.glob("*.brain.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    if path.name == "data" or (path / "brain_reports").is_dir():
        pass
    if not candidates:
        raise StorytellingLoadError(
            f"No Commercial Brain one-slide JSON under {path} "
            "(expected commercial_brain_v1_one_slide.json or brain_reports/*.brain.json)"
        )
    chosen = candidates[0]
    logger.info("storytelling_input path=%s", chosen)
    return extract_one_slide(_read_json(chosen)), chosen
