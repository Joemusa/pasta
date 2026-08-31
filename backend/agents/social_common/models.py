"""Pydantic models for Social & Consumer Intelligence V1. Observations are never invented."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "social_config.yaml"
DEFAULT_TAXONOMY_PATH = SCHEMA_DIR / "social_taxonomy.yaml"

SOCIAL_VERSION = "V1"
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
SentimentLabel = Literal["POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"]
Intensity = Literal["LOW", "MEDIUM", "HIGH"]
TrendLabel = Literal["EMERGING", "GROWING", "STABLE", "DECLINING", "INSUFFICIENT_EVIDENCE"]
SourceStatus = Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE", "INSUFFICIENT_EVIDENCE"]
DataMode = Literal["LIVE", "PARTIAL_LIVE", "TEST_FIXTURES_ONLY", "NO_SOCIAL_DATA"]
AlignmentStatus = Literal[
    "ALIGNED",
    "ALIGNED_OBSERVATION_ONLY",
    "FUTURE_LEAKAGE",
    "INSUFFICIENT_DATES",
]
BrainRelation = Literal[
    "SUPPORTS",
    "CONTRADICTS",
    "ADD_CONTEXT",
    "NEUTRAL",
    "INSUFFICIENT_EVIDENCE",
]


class SocialAgentStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


class SocialConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = "Unilever"
    country: str = "ZA"
    pos_period_start: str = "2026-07-26"
    pos_period_end: str = "2026-08-16"
    excerpt_max_chars: int = 280
    high_min_observations: int = 20
    high_min_sources: int = 3
    medium_min_observations: int = 8
    medium_min_sources: int = 2
    never_high_below_observations: int = 8
    theme_min_observations: int = 2
    trend_min_total: int = 10
    trend_min_recent: int = 5
    trend_growth_ratio: float = 1.5
    causality_forbidden: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def load_social_config(path: Path | None = None) -> SocialConfig:
    target = path or DEFAULT_CONFIG_PATH
    if not target.is_file():
        return SocialConfig()
    payload = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return SocialConfig.model_validate(payload)


class SourceRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    source_type: str
    access_method: str
    status: SourceStatus
    last_successful_collection: str | None = None
    record_count: int = 0
    error: str | None = None
    limitations: list[str] = Field(default_factory=list)


class SocialObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    source: str
    source_type: str
    source_url: str
    author_id_hash: str | None = None
    published_at: str | None = None
    collected_at: str
    brand: str | None = None
    category: str | None = None
    product: str | None = None
    competitor: str | None = None
    region: str | None = None
    country: str | None = None
    text_or_excerpt: str
    language: str | None = None
    engagement: float | None = None
    data_quality: str
    confidence: Confidence
    topics: list[str] = Field(default_factory=list)
    pos_period_start: str | None = None
    pos_period_end: str | None = None
    alignment_method: str | None = None
    alignment_status: AlignmentStatus | None = None


class SentimentBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: SentimentLabel
    intensity: Intensity
    share_positive: float | None = None
    share_negative: float | None = None
    share_neutral: float | None = None
    share_mixed: float | None = None
    positive_negative_ratio: float | None = None
    evidence_count: int
    trend: TrendLabel = "INSUFFICIENT_EVIDENCE"


class ThemeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str
    frequency: int
    sentiment: SentimentLabel
    representative_evidence: list[str] = Field(default_factory=list)
    brands_affected: list[str] = Field(default_factory=list)
    categories_affected: list[str] = Field(default_factory=list)
    consumer_implication: str
    confidence: Confidence
    sources: list[str] = Field(default_factory=list)
    commercial_levers: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)


class TrendRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: TrendLabel
    recent_count: int
    baseline_count: int
    evidence_count: int
    source_count: int
    note: str
    confidence: Confidence


class CommercialContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lever: str
    channel: str
    statement: str
    evidence_count: int
    relation_hint: BrainRelation = "ADD_CONTEXT"


class PeriodWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str | None = None
    end: str | None = None
    pos_period_start: str | None = None
    pos_period_end: str | None = None


class QualityBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_count: int
    source_count: int
    date_range: PeriodWindow
    confidence: Confidence
    limitations: list[str] = Field(default_factory=list)


class SpecialistReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    status: SocialAgentStatus
    version: str = SOCIAL_VERSION
    data_mode: DataMode
    causality_claim: str = "none"
    period: PeriodWindow
    observations: list[SocialObservation] = Field(default_factory=list)
    themes: list[ThemeRecord] = Field(default_factory=list)
    signals: list[TrendRecord] = Field(default_factory=list)
    commercial_context: list[CommercialContext] = Field(default_factory=list)
    sentiment: SentimentBreakdown | None = None
    sentiment_by_dimension: dict[str, SentimentBreakdown] = Field(default_factory=dict)
    source_registry: list[SourceRegistryEntry] = Field(default_factory=list)
    confidence: Confidence
    sources: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    quality: QualityBlock
    report_output_path: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PosStoryCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str | None = None
    dominant_lever: str | None = None
    total_addressable_value_opportunity: float | None = None
    total_addressable_volume_opportunity: float | None = None
    n_actions: int | None = None
    action_brands: list[str] = Field(default_factory=list)
    action_products: list[str] = Field(default_factory=list)
    source_brain_slide: str | None = None


class SocialAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding: str
    relation: BrainRelation
    reason: str
    evidence_count: int
    commercial_levers: list[str] = Field(default_factory=list)


class SocialBrainReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str = "SocialContextBrain"
    status: SocialAgentStatus
    version: str = SOCIAL_VERSION
    data_mode: DataMode
    causality_claim: str = "none"
    verdict: BrainRelation
    pos_story: PosStoryCopy
    alignments: list[SocialAlignment] = Field(default_factory=list)
    themes: list[ThemeRecord] = Field(default_factory=list)
    signals: list[TrendRecord] = Field(default_factory=list)
    commercial_context: list[CommercialContext] = Field(default_factory=list)
    source_registry: list[SourceRegistryEntry] = Field(default_factory=list)
    consumer_context: list[str] = Field(default_factory=list)
    emerging_risks: list[str] = Field(default_factory=list)
    emerging_opportunities: list[str] = Field(default_factory=list)
    quality: QualityBlock
    sources: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    report_output_path: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
