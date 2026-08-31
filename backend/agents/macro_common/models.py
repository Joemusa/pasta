"""Pydantic models for specialist macro agents. Values are sourced, never invented."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "macro_config.yaml"

MACRO_COMMON_VERSION = "V1"
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
Direction = Literal["UP", "DOWN", "UNCHANGED", "INSUFFICIENT"]
SignalStrength = Literal["HIGH", "MEDIUM", "LOW"]
FmcgRelevance = Literal["HIGH", "MEDIUM", "LOW", "NONE"]
AlignmentStatus = Literal[
    "ALIGNED",
    "ALIGNED_WITH_PUBLICATION_LAG",
    "ALIGNED_OBSERVATION_ONLY",
    "FUTURE_LEAKAGE",
    "INSUFFICIENT_DATES",
]
CommercialPressure = Literal["EASING", "TIGHTENING", "MIXED", "NEUTRAL", "INSUFFICIENT"]
BrainRelation = Literal[
    "SUPPORTS",
    "CONTRADICTS",
    "ADD_CONTEXT",
    "NEUTRAL",
    "INSUFFICIENT_EVIDENCE",
]


class MacroAgentStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


class MacroConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = "Unilever"
    pos_period_start: str = "2026-07-26"
    pos_period_end: str = "2026-08-16"
    signal_strength: dict[str, float] = Field(default_factory=dict)
    causality_forbidden: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def load_macro_config(path: Path | None = None) -> MacroConfig:
    target = path or DEFAULT_CONFIG_PATH
    if not target.is_file():
        return MacroConfig()
    payload = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return MacroConfig.model_validate(payload)


class ObservationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_date: str | None = None
    publication_date: str | None = None
    value: float | None = None
    previous_value: float | None = None
    note: str | None = None


class SeriesDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    unit: str
    frequency: str
    date_convention: str = "month_end"
    source: str
    source_url: str
    fmcg_relevance: FmcgRelevance
    commercial_levers: list[str]
    fmcg_channels: list[str]
    higher_is: str
    value_is_period_change: bool = False
    observations: list[ObservationPoint] = Field(default_factory=list)


class MacroCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    version: str = MACRO_COMMON_VERSION
    retrieved_at: str | None = None
    notes: list[str] = Field(default_factory=list)
    series: list[SeriesDefinition] = Field(default_factory=list)


class MacroObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    value: float | None = None
    previous_value: float | None = None
    year_ago_value: float | None = None
    mom_change: float | None = None
    yoy_change: float | None = None
    direction: Direction
    signal_strength: SignalStrength
    fmcg_relevance: FmcgRelevance
    commercial_levers: list[str] = Field(default_factory=list)
    fmcg_channels: list[str] = Field(default_factory=list)
    commercial_pressure: CommercialPressure
    source: str
    source_url: str
    publication_date: str | None = None
    observation_date: str | None = None
    confidence: Confidence
    unit: str
    frequency: str
    pos_period_start: str
    pos_period_end: str
    alignment_method: str
    alignment_status: AlignmentStatus


class MacroSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    summary: str
    direction: Direction
    signal_strength: SignalStrength
    fmcg_relevance: FmcgRelevance
    commercial_levers: list[str] = Field(default_factory=list)
    fmcg_channels: list[str] = Field(default_factory=list)
    commercial_pressure: CommercialPressure
    metrics: list[str] = Field(default_factory=list)
    alignment_status: AlignmentStatus
    confidence: Confidence


class MacroAgentReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    status: MacroAgentStatus
    version: str = MACRO_COMMON_VERSION
    causality_claim: str = "none"
    pos_period_start: str
    pos_period_end: str
    catalog_path: str | None = None
    observations: list[MacroObservation] = Field(default_factory=list)
    signals: list[MacroSignal] = Field(default_factory=list)
    commercial_implications: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    report_output_path: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class BrainAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    metric: str
    relation: BrainRelation
    reason: str
    alignment_status: AlignmentStatus
    commercial_levers: list[str] = Field(default_factory=list)
    fmcg_channels: list[str] = Field(default_factory=list)


class PosStoryCopy(BaseModel):
    """Copied Commercial Brain fields. Macro does not recalculate these."""

    model_config = ConfigDict(extra="forbid")

    headline: str | None = None
    dominant_lever: str | None = None
    total_addressable_value_opportunity: float | None = None
    total_addressable_volume_opportunity: float | None = None
    n_actions: int | None = None
    source_brain_slide: str | None = None


class MacroBrainReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str = "MacroContextBrain"
    status: MacroAgentStatus
    version: str = MACRO_COMMON_VERSION
    causality_claim: str = "none"
    verdict: BrainRelation
    overall_environment: str
    pos_story: PosStoryCopy
    pos_period_start: str
    pos_period_end: str
    alignments: list[BrainAlignment] = Field(default_factory=list)
    specialist_reports: list[str] = Field(default_factory=list)
    observations: list[MacroObservation] = Field(default_factory=list)
    signals: list[MacroSignal] = Field(default_factory=list)
    commercial_implications: list[str] = Field(default_factory=list)
    fmcg_implications: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    report_output_path: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
