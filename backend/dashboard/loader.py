"""Load frozen Commercial Brain, specialist, POS, macro, and social artefacts. No specialist rescoring."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from backend.agents.brain.models import BrainOpportunity, load_brain_config
from backend.agents.social_common.taxonomy import load_taxonomy

_POS_COLUMNS = {
    "product",
    "manufacturer",
    "brand",
    "retailer",
    "region",
    "date",
    "sales_value",
    "sales_volume",
    "store_count",
    "pos_current_price",
}


def _display(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def _latest_json(folder: Path, pattern: str) -> Path | None:
    if not folder.is_dir():
        return None
    matches = sorted(folder.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _resolve_artefact(root: Path, stored: object, folder: str, pattern: str) -> Path | None:
    if stored:
        path = Path(str(stored))
        if path.is_file():
            return path
        nested = root / folder / path.name
        if nested.is_file():
            return nested
    return _latest_json(root / folder, pattern)


def _grain_index(
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
class DashboardStore:
    root: Path
    manufacturer: str
    current_period: str
    period_list: list[str]
    pos_weeks: int
    price_promo_weeks: int | None
    brain: dict[str, Any]
    opportunities: list[BrainOpportunity]
    pos: pd.DataFrame
    brand_to_category: dict[str, str]
    distribution: dict[str, Any]
    price: dict[str, Any]
    promotion: dict[str, Any]
    storytelling: dict[str, Any] | None
    macro: dict[str, Any] | None
    social_status: str
    social_detail: str
    qa_status: str | None
    sources: dict[str, str | None] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    distribution_index: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    price_index: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    promotion_index: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)


def load_store(data_root: str | Path | None = None) -> DashboardStore:
    root = Path(data_root or "backend/data").expanduser().resolve()
    config = load_brain_config()
    brain_path = _latest_json(root / "brain_reports", "*.brain.json")
    brain = _read_json(brain_path)
    if not brain:
        raise FileNotFoundError(f"No Commercial Brain JSON under {root / 'brain_reports'}")
    opportunities = [BrainOpportunity.model_validate(item) for item in brain.get("opportunities") or []]
    integrated = _resolve_artefact(root, brain.get("source_integrated_file"), "integrated", "*.commercial.csv")
    if integrated is None or not integrated.is_file():
        raise FileNotFoundError("Integrated commercial CSV not found")
    header = pd.read_csv(integrated, nrows=0)
    usecols = [column for column in header.columns if column in _POS_COLUMNS]
    pos = pd.read_csv(integrated, usecols=usecols, low_memory=False)
    if "manufacturer" in pos.columns:
        pos = pos[pos["manufacturer"].astype(str).str.casefold() == config.manufacturer.casefold()].copy()
    pos["date"] = pos["date"].astype(str)
    taxonomy = load_taxonomy()
    brand_to_category = {
        str(name): str(spec.get("category"))
        for name, spec in (taxonomy.get("brands") or {}).items()
        if isinstance(spec, dict) and spec.get("category")
    }
    dist_path = _resolve_artefact(
        root, brain.get("source_distribution_report"), "distribution_reports", "*.distribution.json"
    )
    dist = _read_json(dist_path) or {}
    price_path = _resolve_artefact(root, brain.get("source_price_report"), "price_reports", "*.price.json")
    price = _read_json(price_path) or {}
    promo_path = _resolve_artefact(root, brain.get("source_promotion_report"), "promotion_reports", "*.promotion.json")
    promo = _read_json(promo_path) or {}
    story = _read_json(root / "storytelling_reports" / "storytelling_v1_one_slide.json")
    macro = _read_json(root / "macro_context" / "macro_context_v1.json")
    qa = _read_json(_latest_json(root / "qa_reports", "*.qa.json"))
    periods = [
        str(item)
        for item in (dist.get("period_list") or price.get("period_list") or sorted(pos["date"].dropna().unique()))
    ]
    social_status, social_detail = _social_status(root)
    limitations = list(brain.get("limitations") or [])
    limitations.insert(0, "Dashboard V1 is a presentation layer. It does not rescore frozen specialist agents.")
    return DashboardStore(
        root=root,
        manufacturer=str(brain.get("manufacturer") or config.manufacturer),
        current_period=str(brain.get("current_period") or (periods[-1] if periods else "")),
        period_list=periods,
        pos_weeks=int(dist.get("periods_observed") or len(periods)),
        price_promo_weeks=_price_promo_weeks(limitations, price),
        brain=brain,
        opportunities=opportunities,
        pos=pos,
        brand_to_category=brand_to_category,
        distribution=dist,
        price=price,
        promotion=promo,
        storytelling=story,
        macro=macro,
        social_status=social_status,
        social_detail=social_detail,
        qa_status=None if qa is None else str(qa.get("status")),
        sources={
            "brain": _display(brain_path) if brain_path else None,
            "integrated": _display(integrated),
            "distribution": _display(dist_path) if dist_path else None,
            "price": _display(price_path) if price_path else None,
            "promotion": _display(promo_path) if promo_path else None,
            "storytelling": (
                _display(root / "storytelling_reports" / "storytelling_v1_one_slide.json") if story else None
            ),
            "macro": _display(root / "macro_context" / "macro_context_v1.json") if macro else None,
        },
        limitations=limitations,
        distribution_index=_grain_index(dist.get("opportunities"), product_keys=("sku", "product")),
        price_index=_grain_index(price.get("opportunities")),
        promotion_index=_grain_index(promo.get("opportunities")),
    )


def _price_promo_weeks(limitations: list[str], price: dict[str, Any]) -> int | None:
    for note in limitations:
        if "overlapping price/promotion weeks" in note.lower():
            digits = "".join(ch if ch.isdigit() else " " for ch in note).split()
            if digits:
                return int(digits[0])
    observed = price.get("periods_observed")
    return int(observed) if observed is not None else None


def _social_status(root: Path) -> tuple[str, str]:
    gdelt = _read_json(root / "social_live_validation" / "gdelt_smoke_summary.json")
    reddit = _read_json(root / "social_live_validation" / "reddit_smoke_summary.json")
    listening = _read_json(root / "social_reports" / "social_listening_v1.json")
    gdelt_live = bool(gdelt and str(gdelt.get("live_data_status") or "").startswith("LIVE"))
    listening_live = bool(listening and str(listening.get("data_mode") or "") == "LIVE")
    reddit_live = bool(reddit and str(reddit.get("reddit_live_status") or "") == "LIVE")
    if gdelt_live or listening_live:
        n = (gdelt or {}).get("records_successfully_normalised") or len((listening or {}).get("observations") or [])
        return "LIVE — GDELT", f"Supporting context only. {n} normalised GDELT observations. Not a sales driver."
    if reddit_live:
        return "LIVE — REDDIT", "Supporting context only. Not a sales driver."
    return "Not connected", "No live social source is connected. Empty social data is not displayed as live."
