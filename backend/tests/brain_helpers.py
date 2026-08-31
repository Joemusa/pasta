"""Builders for Commercial Brain V1 tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def dist_opp(
    *,
    sku: str = "Handy Andy Lemon 750ml",
    retailer: str = "Checkers",
    region: str = "Gauteng",
    current_stores: float = 4.0,
    benchmark_stores: float = 12.0,
    store_gap: float = 8.0,
    value_per_store: float = 80.0,
    volume_per_store: float = 8.0,
    value_opportunity: float = 640.0,
    volume_opportunity: float = 64.0,
    confidence: str = "HIGH",
) -> dict[str, object]:
    return {
        "opportunity_id": f"2026-08-16|{sku}|{retailer}|{region}",
        "sku": sku,
        "retailer": retailer,
        "region": region,
        "current_stores": current_stores,
        "benchmark_stores": benchmark_stores,
        "store_gap": store_gap,
        "value_per_store": value_per_store,
        "volume_per_store": volume_per_store,
        "value_opportunity": value_opportunity,
        "volume_opportunity": volume_opportunity,
        "benchmark_type": "retailer_peer",
        "confidence": confidence,
        "period": "2026-08-16",
        "benchmark_confidence": confidence,
        "outlier_flags": [],
        "benchmarks_considered": {},
        "sku_identity_field": "product",
    }


def price_opp(
    *,
    product: str = "Handy Andy Lemon 750ml",
    retailer: str = "Checkers",
    region: str = "Gauteng",
    recommendation: str = "LOWER PRICE TEST",
    price_signal: str = "HIGHER_PRICE_LOWER_VOLUME",
    value: float = 400.0,
    volume: float = 20.0,
    confidence: str = "LOW",
    distribution_primary_lever: bool = False,
) -> dict[str, object]:
    return {
        "opportunity_id": f"2026-08-16|{product}|{retailer}|{region}",
        "product": product,
        "brand": "Handy Andy",
        "retailer": retailer,
        "region": region,
        "current_price": 20.0,
        "benchmark_price": 10.0,
        "price_difference_pct": 100.0,
        "price_index": 2.0,
        "volume_per_store": 5.0,
        "value_per_store": 100.0,
        "store_count": 10.0,
        "promotion_status": "NON_PROMOTION",
        "price_signal": price_signal,
        "recommendation": recommendation,
        "estimated_volume_opportunity": volume,
        "estimated_value_opportunity": value,
        "confidence": confidence,
        "sample_size": 7,
        "n_weeks": 4,
        "benchmark_type": "retailer_peer",
        "benchmark_n": 3,
        "mixed_promotion_comparison": False,
        "distribution_primary_lever": distribution_primary_lever,
        "outlier_flags": [],
        "limitations": ["Findings are directional and are not causal elasticity."],
        "methodology": "Estimated price opportunity.",
        "period": "2026-08-16",
        "opportunity_label": "Estimated price opportunity",
    }


def promo_opp(
    *,
    product: str = "Handy Andy Lemon 750ml",
    retailer: str = "Checkers",
    region: str = "Gauteng",
    recommendation: str = "PROMOTE",
    value: float = 300.0,
    volume: float = 15.0,
    confidence: str = "LOW",
    uplift: float = 0.4,
    distribution_primary_lever: bool = False,
    subsidising: bool = False,
) -> dict[str, object]:
    return {
        "opportunity_id": f"2026-08-16|{product}|{retailer}|{region}",
        "product": product,
        "brand": "Handy Andy",
        "retailer": retailer,
        "region": region,
        "promo_observations": 4,
        "non_promo_observations": 4,
        "promo_volume_per_store": 14.0,
        "non_promo_volume_per_store": 10.0,
        "volume_uplift_pct": uplift,
        "promo_value_per_store": 112.0,
        "non_promo_value_per_store": 100.0,
        "value_uplift_pct": 0.12,
        "promo_price": 8.0,
        "normal_price": None,
        "price_discount_pct": None,
        "estimated_incremental_volume": volume,
        "estimated_incremental_value": value,
        "recommendation": recommendation,
        "confidence": confidence,
        "outlier_flag": False,
        "outlier_flags": [],
        "limitations": ["Findings are estimated promotional opportunity, not causal incrementality."],
        "methodology": "Estimated promotional opportunity.",
        "period": "2026-08-16",
        "opportunity_label": "Estimated promotional opportunity",
        "distribution_primary_lever": distribution_primary_lever,
        "subsidising_existing_demand": subsidising,
        "mixed_promotion_window": False,
    }


def write_bundle(
    tmp_path: Path,
    *,
    dist: list[dict[str, object]] | None = None,
    price: list[dict[str, object]] | None = None,
    promo: list[dict[str, object]] | None = None,
) -> Path:
    root = tmp_path / "data"
    write_json(
        root / "distribution_reports" / "panel.distribution.json",
        {
            "opportunity_label": "Estimated distribution opportunity",
            "manufacturer": "Unilever",
            "current_period": "2026-08-16",
            "sku_identity_field": "product",
            "opportunities": dist or [],
            "limitations": ["4 POS weeks currently available."],
        },
    )
    write_json(
        root / "price_reports" / "panel.price.json",
        {
            "status": "READY WITH WARNINGS",
            "version": "V1",
            "frozen": True,
            "current_period": "2026-08-16",
            "manufacturer": "Unilever",
            "opportunities": price or [],
            "limitations": ["Findings are directional and are not causal elasticity."],
        },
    )
    write_json(
        root / "promotion_reports" / "panel.promotion.json",
        {
            "status": "READY WITH WARNINGS",
            "version": "V1",
            "frozen": True,
            "current_period": "2026-08-16",
            "manufacturer": "Unilever",
            "opportunities": promo or [],
            "limitations": ["Findings are estimated promotional opportunity, not causal incrementality."],
        },
    )
    return root
