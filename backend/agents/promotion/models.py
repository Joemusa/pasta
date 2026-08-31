"""Pydantic models and configuration for Promotion Agent V1."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "promotion_config.yaml"

PROMOTION_AGENT_VERSION = "V1"

V1_LIMITATIONS = [
    "4 POS weeks currently available.",
    "3 overlapping price/promotion weeks.",
    "Promotion Indicator 0/1 in the source extract is a stacked state, not a grain-level promo flag.",
    "No proven normal/RSP field; off_promo_rsp / on_promo_rsp is not treated as normal shelf price.",
    "NORMAL_PRICE_UNAVAILABLE unless a proven normal-price field exists.",
    "PROMOTION_TYPE_UNAVAILABLE; the extract has no price-discount / multibuy / loyalty type.",
    "Rolling 4 Weeks CY metrics may not be independent observations.",
    "Promotion metrics can be missing; missing is not converted to zero.",
    "ProductsID is not the canonical join key; SKU identity is product name.",
    "Current opportunity estimates use the documented 0.25 capture-rate methodology.",
    "Estimates are not guaranteed incremental sales.",
    "Findings are estimated promotional opportunity, not causal incrementality.",
    "HIGH confidence requires 8 or more weeks; that threshold is not relaxed in V1.",
]

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
JOIN_KEY = ("product", "retailer", "region", "date")
GRAIN = ("product", "retailer", "region")


class PromoState(StrEnum):
    PROMOTION = "PROMOTION"
    NON_PROMOTION = "NON_PROMOTION"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class PromoIntensity(StrEnum):
    HIGH = "HIGH"
    MID = "MID"
    LOW = "LOW"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class BaselineKind(StrEnum):
    NON_PROMO = "non_promo"
    LOW_PROMO_INTENSITY = "low_promo_intensity"
    NONE = "none"


class Recommendation(StrEnum):
    PROMOTE = "PROMOTE"
    PROMOTE_MORE_SELECTIVELY = "PROMOTE MORE SELECTIVELY"
    MAINTAIN_CURRENT_PROMOTION = "MAINTAIN CURRENT PROMOTION"
    REDUCE_PROMOTION = "REDUCE PROMOTION"
    DO_NOT_PROMOTE = "DO NOT PROMOTE"
    DISTRIBUTION_FIRST = "DISTRIBUTION FIRST"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"


class PrimaryLever(StrEnum):
    PROMOTION = "PROMOTION"
    PRICE = "PRICE"
    DISTRIBUTION = "DISTRIBUTION"
    OVERLAP = "OVERLAP"
    UNCLEAR = "UNCLEAR"


class PromotionType(StrEnum):
    PRICE_DISCOUNT = "price discount"
    MULTIBUY = "multibuy"
    LOYALTY = "loyalty"
    OTHER = "other"
    UNKNOWN = "unknown"
    UNAVAILABLE = "PROMOTION_TYPE_UNAVAILABLE"


class PromotionAgentStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


class PromotionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = "Unilever"
    opportunity_label: str = "Estimated promotional opportunity"
    min_promo_observations: int = 2
    min_non_promo_observations: int = 2
    min_weeks_for_recommendation: int = 3
    min_history_for_high_confidence: int = 8
    min_history_for_medium_confidence: int = 3
    promo_percent_threshold: float = 0.0
    low_promo_intensity_max: float = 25.0
    high_promo_intensity_min: float = 50.0
    strong_volume_uplift_pct: float = 0.15
    weak_volume_uplift_pct: float = 0.05
    strong_value_uplift_pct: float = 0.10
    weak_value_uplift_pct: float = 0.00
    low_distribution_ratio: float = 0.5
    high_distribution_ratio: float = 0.80
    low_sales_ratio: float = 0.5
    min_store_gap: float = 1.0
    distribution_change_ratio: float = 0.50
    capture_rate: float = 0.25
    min_value_opportunity: float = 1.0
    mad_threshold: float = 3.5
    peer_statistic: str = "median"
    output_top_n: int = 10
    output_top_opportunities: int = 20


class PromotionOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    product: str
    brand: str | None = None
    retailer: str
    region: str
    promo_observations: int = 0
    non_promo_observations: int = 0
    promo_volume_per_store: float | None = None
    non_promo_volume_per_store: float | None = None
    volume_uplift_pct: float | None = None
    promo_value_per_store: float | None = None
    non_promo_value_per_store: float | None = None
    value_uplift_pct: float | None = None
    promo_price: float | None = None
    normal_price: float | None = None
    price_discount_pct: float | None = None
    estimated_incremental_volume: float = 0.0
    estimated_incremental_value: float = 0.0
    recommendation: str
    confidence: Confidence
    outlier_flag: bool = False
    outlier_flags: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    methodology: str
    period: str
    opportunity_label: str = "Estimated promotional opportunity"
    promotion_status: str = PromoState.UNKNOWN.value
    promo_intensity: str = PromoIntensity.UNKNOWN.value
    baseline_kind: str = BaselineKind.NONE.value
    promotion_type: str = PromotionType.UNAVAILABLE.value
    normal_price_status: str = "NORMAL_PRICE_UNAVAILABLE"
    n_weeks: int = 0
    store_count: float | None = None
    distribution_primary_lever: bool = False
    subsidising_existing_demand: bool = False
    overlaps_price_opportunity: bool = False
    overlaps_distribution_opportunity: bool = False
    primary_lever: str = PrimaryLever.UNCLEAR.value
    mixed_promotion_window: bool = False


class PromoMover(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    estimated_incremental_value: float
    estimated_incremental_volume: float
    skus: int
    regions: int = 0
    retailers: int = 0
    opportunities: int
    average_uplift: float | None = None
    average_confidence: str
    confidence_mix: dict[str, int] = Field(default_factory=dict)


class PromotionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PromotionAgentStatus
    version: str = PROMOTION_AGENT_VERSION
    opportunity_label: str = "Estimated promotional opportunity"
    causality_claim: str = "none"
    manufacturer: str
    current_period: str
    grain: list[str] = Field(default_factory=lambda: list(GRAIN))
    source_integrated_file: str
    input_path: str
    periods_observed: int
    period_list: list[str] = Field(default_factory=list)
    unilever_rows: int = 0
    current_period_rows: int = 0
    evaluated_grains: int = 0
    opportunities_emitted: int = 0
    recommendation_counts: dict[str, int] = Field(default_factory=dict)
    promotion_uplift_summary: dict[str, int] = Field(default_factory=dict)
    promotion_investment_priorities: list[PromoMover] = Field(default_factory=list)
    promotion_risks: list[PromotionOpportunity] = Field(default_factory=list)
    total_incremental_value: float = 0.0
    total_incremental_volume: float = 0.0
    confidence_distribution: dict[str, int] = Field(default_factory=dict)
    distribution_primary_count: int = 0
    price_primary_count: int = 0
    promotion_primary_count: int = 0
    overlap_flag_count: int = 0
    outlier_dependent_top_opportunities: int = 0
    top_promotional_opportunities: list[PromotionOpportunity] = Field(default_factory=list)
    top_retailers: list[PromoMover] = Field(default_factory=list)
    top_skus: list[PromoMover] = Field(default_factory=list)
    top_regions: list[PromoMover] = Field(default_factory=list)
    opportunities: list[PromotionOpportunity] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    report_output_path: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"YAML at {path} must be a mapping")
    return payload


def load_promotion_config(path: Path | None = None) -> PromotionConfig:
    return PromotionConfig.model_validate(_read_yaml(path or DEFAULT_CONFIG_PATH))
