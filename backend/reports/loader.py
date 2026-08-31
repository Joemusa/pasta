"""Load frozen Commercial Brain, storytelling, specialist, macro, and social artefacts. No rescoring."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def display_path(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def latest_json(folder: Path, pattern: str) -> Path | None:
    if not folder.is_dir():
        return None
    matches = sorted(folder.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def resolve_artefact(root: Path, stored: object, folder: str, pattern: str) -> Path | None:
    if stored:
        path = Path(str(stored))
        if path.is_file():
            return path
        nested = root / folder / path.name
        if nested.is_file():
            return nested
    return latest_json(root / folder, pattern)


def grain_index(
    rows: list[Any] | None, *, product_keys: tuple[str, ...] = ("product", "sku")
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        product = ""
        for key in product_keys:
            if row.get(key):
                product = str(row.get(key))
                break
        index[(product, str(row.get("retailer") or ""), str(row.get("region") or ""))] = row
    return index


@dataclass
class ReportInputs:
    root: Path
    brain_path: Path
    brain: dict[str, Any]
    storytelling_path: Path | None
    storytelling: dict[str, Any] | None
    distribution_path: Path | None
    distribution_index: dict[tuple[str, str, str], dict[str, Any]]
    macro_path: Path | None
    macro: dict[str, Any] | None
    social: dict[str, Any]
    sources: dict[str, str | None] = field(default_factory=dict)


def social_block(root: Path) -> dict[str, Any]:
    gdelt = read_json(root / "social_live_validation" / "gdelt_smoke_summary.json")
    reddit = read_json(root / "social_live_validation" / "reddit_smoke_summary.json")
    listening = read_json(root / "social_reports" / "social_listening_v1.json")
    gdelt_live = bool(gdelt and str(gdelt.get("live_data_status") or "").startswith("LIVE"))
    listening_live = bool(listening and str(listening.get("data_mode") or "") == "LIVE")
    reddit_live = bool(reddit and str(reddit.get("reddit_live_status") or "") == "LIVE")
    if not (gdelt_live or listening_live or reddit_live):
        return {
            "connected": False,
            "status": "not connected",
            "display": "Social intelligence: not connected",
            "kind": "OBSERVATION",
            "source": None,
            "source_url": None,
            "observation_start": None,
            "observation_end": None,
            "validated_observations": [],
            "disclaimer": "No live social source is connected. Empty social data is not displayed as live.",
        }
    pack = gdelt or listening or {}
    observations: list[dict[str, str]] = []
    n = pack.get("records_successfully_normalised") or pack.get("records_successfully_analysed")
    analysed = pack.get("records_successfully_analysed")
    if n:
        text = f"{n} normalised public-web observations"
        if analysed:
            text += f" ({analysed} analysed)"
        observations.append({"text": text + ".", "kind": "OBSERVATION"})
    brands = pack.get("top_brands_detected") or []
    if brands:
        observations.append(
            {"text": "Brands detected: " + ", ".join(str(item) for item in brands) + ".", "kind": "OBSERVATION"}
        )
    sentiment = pack.get("sentiment") if isinstance(pack.get("sentiment"), dict) else None
    if sentiment and sentiment.get("label"):
        observations.append(
            {
                "text": f"Sentiment label {sentiment.get('label')} (observation, not a sales driver).",
                "kind": "OBSERVATION",
            }
        )
    source_name = "GDELT" if gdelt_live or listening_live else "REDDIT"
    return {
        "connected": True,
        "status": "LIVE — GDELT" if source_name == "GDELT" else "LIVE — REDDIT",
        "display": f"Social intelligence: LIVE — {source_name}",
        "kind": "OBSERVATION",
        "source": source_name,
        "source_url": "http://api.gdeltproject.org/api/v2/doc/doc" if source_name == "GDELT" else None,
        "observation_start": pack.get("observation_start"),
        "observation_end": pack.get("observation_end") or pack.get("collection_timestamp"),
        "validated_observations": observations,
        "disclaimer": (
            "Supporting context only. Social observations do not cause POS gaps and are not commercial actions."
        ),
    }


def load_inputs(data_root: str | Path | None = None) -> ReportInputs:
    root = Path(data_root or "backend/data").expanduser().resolve()
    brain_path = latest_json(root / "brain_reports", "*.brain.json")
    brain = read_json(brain_path)
    if brain_path is None or not brain:
        raise FileNotFoundError(f"No Commercial Brain JSON under {root / 'brain_reports'}")
    story_path = root / "storytelling_reports" / "storytelling_v1_one_slide.json"
    story = read_json(story_path)
    dist_path = resolve_artefact(
        root, brain.get("source_distribution_report"), "distribution_reports", "*.distribution.json"
    )
    dist = read_json(dist_path) or {}
    macro_path = root / "macro_context" / "macro_context_v1.json"
    macro = read_json(macro_path)
    price_path = resolve_artefact(root, brain.get("source_price_report"), "price_reports", "*.price.json")
    promo_path = resolve_artefact(root, brain.get("source_promotion_report"), "promotion_reports", "*.promotion.json")
    integrated = resolve_artefact(root, brain.get("source_integrated_file"), "integrated", "*.commercial.csv")
    return ReportInputs(
        root=root,
        brain_path=brain_path,
        brain=brain,
        storytelling_path=story_path if story else None,
        storytelling=story,
        distribution_path=dist_path,
        distribution_index=grain_index(dist.get("opportunities"), product_keys=("sku", "product")),
        macro_path=macro_path if macro else None,
        macro=macro,
        social=social_block(root),
        sources={
            "brain": display_path(brain_path),
            "storytelling": display_path(story_path) if story else None,
            "distribution": display_path(dist_path) if dist_path else None,
            "price": display_path(price_path) if price_path else None,
            "promotion": display_path(promo_path) if promo_path else None,
            "integrated": display_path(integrated) if integrated else None,
            "macro": display_path(macro_path) if macro else None,
        },
    )
