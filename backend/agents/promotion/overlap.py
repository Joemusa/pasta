"""Read persisted Distribution and Price reports for overlap flags.

Does not re-run those frozen agents and does not combine opportunities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def _grain_key(product: str, retailer: str, region: str) -> str:
    return f"{product}|{retailer}|{region}"


@dataclass
class OverlapIndex:
    price_grains: set[str] = field(default_factory=set)
    price_recommendations: dict[str, str] = field(default_factory=dict)
    distribution_grains: set[str] = field(default_factory=set)

    def price_recommendation(self, product: str, retailer: str, region: str) -> str | None:
        return self.price_recommendations.get(_grain_key(product, retailer, region))

    def has_price(self, product: str, retailer: str, region: str) -> bool:
        return _grain_key(product, retailer, region) in self.price_grains

    def has_distribution(self, product: str, retailer: str, region: str) -> bool:
        return _grain_key(product, retailer, region) in self.distribution_grains


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _opportunity_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("opportunities")
    if not isinstance(raw, list) or not raw:
        raw = payload.get("top_opportunities") or payload.get("top_price_opportunities") or []
    return [item for item in raw if isinstance(item, dict)]


def load_overlap_index(data_root: Path, stem: str) -> OverlapIndex:
    index = OverlapIndex()
    price_path = data_root / "price_reports" / f"{stem}.price.json"
    dist_path = data_root / "distribution_reports" / f"{stem}.distribution.json"
    price_payload = _load_json(price_path)
    if price_payload:
        for row in _opportunity_rows(price_payload):
            product = str(row.get("product") or row.get("sku") or "").strip()
            retailer = str(row.get("retailer") or "").strip()
            region = str(row.get("region") or "").strip()
            if not product or not retailer or not region:
                continue
            key = _grain_key(product, retailer, region)
            index.price_grains.add(key)
            rec = row.get("recommendation")
            if rec:
                index.price_recommendations[key] = str(rec)
    dist_payload = _load_json(dist_path)
    if dist_payload:
        for row in _opportunity_rows(dist_payload):
            product = str(row.get("sku") or row.get("product") or "").strip()
            retailer = str(row.get("retailer") or "").strip()
            region = str(row.get("region") or "").strip()
            if not product or not retailer or not region:
                continue
            index.distribution_grains.add(_grain_key(product, retailer, region))
    return index
