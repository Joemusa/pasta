"""Pydantic models and configuration for the Distribution Agent."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "distribution_config.yaml"

Confidence = Literal["HIGH", "MEDIUM", "LOW"]


class BenchmarkType(StrEnum):
    HISTORICAL_PEAK = "historical_peak"
    HISTORICAL_AVERAGE = "historical_average"
    RECENT_HIGH = "recent_high"
    RETAILER_PEER = "retailer_peer"
    REGIONAL_PEER = "regional_peer"


class DistributionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = "Unilever"
    recent_periods: int = 2
    min_peer_observations: int = 3
    peer_statistic: str = "median"
    spike_ratio: float = 1.5
    min_periods_to_flag_spike: int = 3
    min_store_gap: float = 1.0
    min_history_for_high_confidence: int = 4
    min_history_for_medium_confidence: int = 2
    value_per_store_cv_threshold: float = 0.35
    mad_threshold: float = 3.5
    peer_scale_ratio: float = 4.0
    output_top_n: int = 10


class BenchmarkSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stores: float | None = None
    available: bool = False
    flagged_spike: bool = False
    observations: int = 0
    selected: bool = False


class Opportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    sku: str
    retailer: str
    region: str
    current_stores: float
    benchmark_stores: float
    store_gap: float
    value_per_store: float
    volume_per_store: float
    value_opportunity: float
    volume_opportunity: float
    benchmark_type: str
    confidence: Confidence
    period: str
    benchmark_confidence: Confidence
    outlier_flags: list[str] = Field(default_factory=list)
    benchmarks_considered: dict[str, BenchmarkSnapshot] = Field(default_factory=dict)
    sku_identity_field: str = "sku"


class NeedleMover(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    total_value_opportunity: float
    total_volume_opportunity: float
    affected_skus: int
    affected_regions: int
    affected_retailers: int = 0
    affected_stores: float
    priority_skus: int
    current_sales_value: float = 0.0


class DistributionReport(BaseModel):
    """Structured distribution output. Opportunities are estimated, not guaranteed sales."""

    model_config = ConfigDict(extra="forbid")

    opportunity_label: str = "Estimated distribution opportunity"
    manufacturer: str
    current_period: str
    sku_identity_field: str
    grain: list[str] = Field(default_factory=lambda: ["sku", "retailer", "region"])
    source_clean_file: str
    input_path: str
    periods_observed: int
    period_list: list[str] = Field(default_factory=list)
    unilever_rows: int = 0
    current_period_rows: int = 0
    opportunities_emitted: int = 0
    skipped_missing: int = 0
    skipped_no_gap: int = 0
    skipped_no_rate: int = 0
    total_value_opportunity: float = 0.0
    total_volume_opportunity: float = 0.0
    confidence_distribution: dict[str, int] = Field(default_factory=dict)
    top_retailers: list[NeedleMover] = Field(default_factory=list)
    top_regions: list[NeedleMover] = Field(default_factory=list)
    top_skus: list[NeedleMover] = Field(default_factory=list)
    top_opportunities: list[Opportunity] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    flagged_outlier_count: int = 0
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


def load_distribution_config(path: Path | None = None) -> DistributionConfig:
    return DistributionConfig.model_validate(_read_yaml(path or DEFAULT_CONFIG_PATH))
