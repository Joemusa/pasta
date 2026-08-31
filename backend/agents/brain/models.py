"""Pydantic models and configuration for Commercial Brain V1."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "brain_config.yaml"

BRAIN_VERSION = "V1"
Confidence = Literal["HIGH", "MEDIUM", "LOW"]

V1_LIMITATIONS = [
    "4 POS weeks currently available.",
    "3 overlapping price/promotion weeks.",
    "No proven normal/RSP field; off_promo_rsp / on_promo_rsp is not treated as normal shelf price.",
    "PROMOTION_TYPE_UNAVAILABLE; the extract has no price-discount / multibuy / loyalty type.",
    "Rolling 4 Weeks CY metrics may not be independent observations.",
    "Promotion metrics can be missing; missing is not converted to zero.",
    "ProductsID is not the canonical join key; SKU identity is product name.",
    "Short price/promotion history; HIGH confidence is not manufactured.",
    "Opportunity estimates are directional and are not guaranteed incremental sales.",
    "No causal elasticity and no causal promotion incrementality.",
    "Specialist Distribution, Price, and Promotion agents are frozen; the Brain does not re-score them.",
    "Overlapping levers are not summed; the reported value is the primary commercial opportunity.",
]


class DominantLever(StrEnum):
    DISTRIBUTION = "DISTRIBUTION"
    PRICE = "PRICE"
    PROMOTION = "PROMOTION"
    MULTI_LEVER = "MULTI-LEVER"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"


class DoubleCountingRisk(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class BrainAgentStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


class BrainConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = "Unilever"
    n_actions: int = 3
    min_store_gap: float = 1.0
    min_value_per_store: float = 0.01
    min_primary_value: float = 1.0
    promo_vs_price_ratio: float = 1.0
    min_promo_uplift: float = 0.05
    value_reference: float = 10000.0
    evidence_high: float = 1.0
    evidence_medium: float = 0.70
    evidence_low: float = 0.45
    actionability_single: float = 1.0
    actionability_multi: float = 0.90
    actionability_insufficient: float = 0.0
    data_quality_base: float = 1.0
    outlier_penalty: float = 0.15
    mixed_promo_penalty: float = 0.10
    max_actions_per_product: int = 2
    max_actions_per_lever: int = 2
    min_action_volume: float = 0.01
    output_top_n: int = 10


class BrainOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    product: str
    brand: str | None = None
    retailer: str
    region: str
    dominant_lever: str
    secondary_lever: str | None = None
    overlap: bool = False
    gross_estimated_value: float = 0.0
    gross_estimated_volume: float = 0.0
    primary_lever_value: float = 0.0
    primary_lever_volume: float = 0.0
    secondary_lever_value: float = 0.0
    secondary_lever_volume: float = 0.0
    double_counting_risk: str = DoubleCountingRisk.NONE.value
    opportunity_value: float = 0.0
    opportunity_volume: float = 0.0
    current_sales: float | None = None
    current_volume: float | None = None
    sales_per_store: float | None = None
    volume_per_store: float | None = None
    distribution_stores: float | None = None
    distribution_gap: float | None = None
    price_signal: str | None = None
    promotion_signal: str | None = None
    priority_score: float = 0.0
    confidence: Confidence
    recommended_action: str
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class BrainAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    action_number: int
    lever: str
    headline: str
    why: str
    product: str
    brand: str | None = None
    retailer: str
    region: str
    estimated_value: float
    estimated_volume: float
    confidence: Confidence
    recommended_action: str
    evidence: list[str] = Field(default_factory=list)
    priority_score: float = 0.0


class BrainMover(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    estimated_value: float
    estimated_volume: float
    dominant_lever: str
    opportunities: int
    skus: int = 0
    regions: int = 0
    retailers: int = 0
    evidence_strength: str
    confidence_mix: dict[str, int] = Field(default_factory=dict)
    recommended_action: str | None = None
    top_retailer: str | None = None
    top_sku: str | None = None


class BrainSkuPriority(BaseModel):
    """Grain-level SKU action, not a product-only roll-up."""

    model_config = ConfigDict(extra="forbid")

    product: str
    brand: str | None = None
    retailer: str
    region: str
    dominant_lever: str
    opportunity_value: float
    opportunity_volume: float
    current_sales: float | None = None
    sales_per_store: float | None = None
    distribution: float | None = None
    price_signal: str | None = None
    promotion_signal: str | None = None
    priority_score: float
    confidence: Confidence
    recommended_action: str


class Storytelling(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_message: str
    supporting_actions: list[str] = Field(default_factory=list)
    quantified_opportunity: str
    next_step: str


class OneSlide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_title: str
    headline: str
    headline_support: str
    total_estimated_value_opportunity: float
    total_estimated_volume_opportunity: float
    top_actions: list[dict[str, Any]] = Field(default_factory=list)
    retailer_priorities: list[dict[str, Any]] = Field(default_factory=list)
    sku_priorities: list[dict[str, Any]] = Field(default_factory=list)
    region_priorities: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    methodology: str
    data_coverage: str


class BrainReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: BrainAgentStatus
    version: str = BRAIN_VERSION
    manufacturer: str
    current_period: str
    causality_claim: str = "none"
    opportunity_label: str = "Estimated commercial opportunity"
    source_distribution_report: str | None = None
    source_price_report: str | None = None
    source_promotion_report: str | None = None
    source_integrated_file: str | None = None
    input_path: str
    grains_evaluated: int = 0
    opportunities_emitted: int = 0
    double_counting_conflicts_resolved: int = 0
    lever_distribution: dict[str, int] = Field(default_factory=dict)
    confidence_distribution: dict[str, int] = Field(default_factory=dict)
    total_estimated_value_opportunity: float = 0.0
    total_estimated_volume_opportunity: float = 0.0
    headline: str
    storytelling: Storytelling
    top_actions: list[BrainAction] = Field(default_factory=list)
    top_retailers: list[BrainMover] = Field(default_factory=list)
    top_skus: list[BrainSkuPriority] = Field(default_factory=list)
    top_regions: list[BrainMover] = Field(default_factory=list)
    opportunities: list[BrainOpportunity] = Field(default_factory=list)
    one_slide: OneSlide
    risks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    methodology: str
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


def load_brain_config(path: Path | None = None) -> BrainConfig:
    return BrainConfig.model_validate(_read_yaml(path or DEFAULT_CONFIG_PATH))
