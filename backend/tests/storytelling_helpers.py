"""Builders for Storytelling Engine V1 tests."""

from __future__ import annotations

import json
from pathlib import Path


def brain_action(
    *,
    rank: int = 1,
    lever: str = "DISTRIBUTION",
    product: str = "Sunlight Pine Gel 500ml",
    brand: str = "Sunlight",
    retailer: str = "Shoprite",
    region: str = "Free State",
    addressable_value: float = 4534.32,
    addressable_volume: float = 84.0,
    confidence: str = "HIGH",
    store_gap: float = 24.0,
    current_sales: float = 188.93,
) -> dict[str, object]:
    return {
        "rank": rank,
        "lever": lever,
        "headline": f"Expand distribution of {product} in {region}",
        "product": product,
        "brand": brand,
        "retailer": retailer,
        "region": region,
        "estimated_value": addressable_value,
        "estimated_volume": addressable_volume,
        "addressable_value": addressable_value,
        "addressable_volume": addressable_volume,
        "addressable_value_opportunity": addressable_value,
        "addressable_volume_opportunity": addressable_volume,
        "current_sales": current_sales,
        "confidence": confidence,
        "why": (
            f"Coverage sits {store_gap:.0f} stores below the like-for-like benchmark at {retailer} "
            f"in {region}. Addressable value is not guaranteed incremental sales."
        ),
        "recommended_action": (
            f"Brief a distribution expansion for {product} at {retailer} in {region}: close a "
            f"{store_gap:.0f}-store gap."
        ),
        "evidence": [
            f"Distribution addressable value = value/store 188.93 x store gap {store_gap:.1f}. "
            f"This is the gap-closing opportunity, not guaranteed incremental sales.",
            f"Current sales R{current_sales:,.0f} (distinct from addressable value; not the opportunity).",
        ],
    }


def brain_one_slide(
    *,
    actions: list[dict[str, object]] | None = None,
    total_value: float = 588562.67,
    total_volume: float = 14521.165,
) -> dict[str, object]:
    cards = actions or [
        brain_action(rank=1, store_gap=24.0, addressable_value=4534.32, addressable_volume=84.0),
        brain_action(
            rank=2,
            product="Sunlight Pine Gel 1l",
            region="Gauteng",
            store_gap=13.0,
            addressable_value=2709.84,
            addressable_volume=54.2237,
            current_sales=31684.3,
        ),
        brain_action(
            rank=3,
            product="Handy Andy All Purpose Cleaner Eucalyptus 5l",
            brand="Handy Andy",
            retailer="Makro Online",
            region="Gauteng",
            store_gap=3.0,
            addressable_value=2653.32,
            addressable_volume=73.125,
            current_sales=7075.53,
        ),
    ]
    return {
        "report_title": "Unilever Commercial Brain V1",
        "headline": "Distribution is currently the clearest growth lever in the priority opportunities",
        "headline_support": "Addressable value and addressable volume are not guaranteed incremental sales.",
        "total_estimated_value_opportunity": total_value,
        "total_estimated_volume_opportunity": total_volume,
        "total_addressable_value_opportunity": total_value,
        "total_addressable_volume_opportunity": total_volume,
        "top_actions": cards,
        "retailer_priorities": [],
        "sku_priorities": [],
        "region_priorities": [],
        "risks": ["Addressable value and addressable volume are not guaranteed incremental sales."],
        "limitations": [
            "4 POS weeks currently available.",
            "3 overlapping price/promotion weeks.",
        ],
        "methodology": "Primary-lever addressable value only.",
        "data_coverage": "4 POS weeks",
    }


def write_one_slide(path: Path, payload: dict[str, object] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or brain_one_slide()), encoding="utf-8")
    return path


def macro_pack(
    *,
    signal: str = "Consumer pressure increasing",
    evidence: str = "FNB/BER CCI = -19",
    direction: str = "NEGATIVE",
    relevance: str = "HIGH",
    supports_pos_story: bool = True,
    commercial_implication: str = (
        "Consumers are likely to remain value-conscious, increasing the importance of "
        "availability and targeted price/promotion execution."
    ),
    confidence: str = "HIGH",
    sources: list[str] | None = None,
) -> dict[str, object]:
    return {
        "version": "V1",
        "role": "supporting_context",
        "signal": signal,
        "evidence": evidence,
        "direction": direction,
        "relevance": relevance,
        "supports_pos_story": supports_pos_story,
        "commercial_implication": commercial_implication,
        "confidence": confidence,
        "sources": sources or ["SARB", "BER", "Stats SA"],
        "evidence_as_of": None,
    }


def write_macro_pack(data_root: Path, payload: dict[str, object] | None = None) -> Path:
    path = data_root / "macro_context" / "macro_context_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or macro_pack()), encoding="utf-8")
    return path
