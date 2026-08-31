"""Pydantic models and configuration for Price Agent V1."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "price_config.yaml"

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
JOIN_KEY = ("product", "retailer", "region", "date")
GRAIN = ("product", "retailer", "region")


class PromotionStatus(StrEnum):
    PROMOTION = "PROMOTION"
    NON_PROMOTION = "NON_PROMOTION"
    UNKNOWN = "UNKNOWN"


class Recommendation(StrEnum):
    MAINTAIN_PRICE = "MAINTAIN PRICE"
    LOWER_PRICE_TEST = "LOWER PRICE TEST"
    PRICE_INCREASE_TEST = "PRICE INCREASE TEST"
    PRICE_ARCHITECTURE_REVIEW = "PRICE ARCHITECTURE REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"


class PriceSignal(StrEnum):
    HIGHER_PRICE_LOWER_VOLUME = "HIGHER_PRICE_LOWER_VOLUME"
    LOWER_PRICE_HIGHER_VOLUME = "LOWER_PRICE_HIGHER_VOLUME"
    HIGHER_PRICE_STABLE_VOLUME = "HIGHER_PRICE_STABLE_VOLUME"
    LOWER_PRICE_LOWER_VALUE = "LOWER_PRICE_LOWER_VALUE"
    ALIGNED = "ALIGNED"
    UNCLEAR = "UNCLEAR"


class BenchmarkType(StrEnum):
    RETAILER_PEER = "retailer_peer"
    REGIONAL_PEER = "regional_peer"
    CATEGORY_PEER = "category_peer"
    HISTORICAL = "historical"
    SKU_NETWORK = "sku_network"
    NONE = "none"


class PriceAgentStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


class PriceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = "Unilever"
    opportunity_label: str = "Estimated price opportunity"
    min_peer_observations: int = 3
    min_historical_observations: int = 2
    min_weeks_for_recommendation: int = 3
    min_history_for_high_confidence: int = 8
    min_history_for_medium_confidence: int = 3
    price_gap_pct: float = 0.05
    volume_gap_pct: float = 0.10
    value_gap_pct: float = 0.10
    promo_percent_threshold: float = 0.0
    low_distribution_ratio: float = 0.5
    low_sales_ratio: float = 0.5
    min_store_gap: float = 1.0
    capture_rate: float = 0.25
    architecture_spread_ratio: float = 1.25
    min_architecture_locations: int = 3
    min_value_opportunity: float = 1.0
    mad_threshold: float = 3.5
    peer_statistic: str = "median"
    output_top_n: int = 10


class PriceOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    product: str
    brand: str | None = None
    retailer: str
    region: str
    current_price: float
    benchmark_price: float | None = None
    price_difference_pct: float | None = None
    price_index: float | None = None
    volume_per_store: float | None = None
    value_per_store: float | None = None
    store_count: float | None = None
    promotion_status: str
    price_signal: str
    recommendation: str
    estimated_volume_opportunity: float = 0.0
    estimated_value_opportunity: float = 0.0
    confidence: Confidence
    sample_size: int = 0
    n_weeks: int = 0
    benchmark_type: str = BenchmarkType.NONE.value
    benchmark_n: int = 0
    mixed_promotion_comparison: bool = False
    distribution_primary_lever: bool = False
    outlier_flags: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    methodology: str
    period: str
    opportunity_label: str = "Estimated price opportunity"


class PriceMover(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    estimated_value_opportunity: float
    estimated_volume_opportunity: float
    skus: int
    regions: int = 0
    retailers: int = 0
    opportunities: int
    average_confidence: str
    confidence_mix: dict[str, int] = Field(default_factory=dict)


class PriceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PriceAgentStatus
    opportunity_label: str = "Estimated price opportunity"
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
    price_signal_summary: dict[str, int] = Field(default_factory=dict)
    total_value_opportunity: float = 0.0
    total_volume_opportunity: float = 0.0
    confidence_distribution: dict[str, int] = Field(default_factory=dict)
    top_price_opportunities: list[PriceOpportunity] = Field(default_factory=list)
    top_retailers: list[PriceMover] = Field(default_factory=list)
    top_skus: list[PriceMover] = Field(default_factory=list)
    top_regions: list[PriceMover] = Field(default_factory=list)
    opportunities: list[PriceOpportunity] = Field(default_factory=list)
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


def load_price_config(path: Path | None = None) -> PriceConfig:
    return PriceConfig.model_validate(_read_yaml(path or DEFAULT_CONFIG_PATH))
