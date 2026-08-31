"""Pydantic models for Storytelling Engine V1. Commercial Brain values are copied, not recalculated."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

STORYTELLING_VERSION = "V1"
Confidence = Literal["HIGH", "MEDIUM", "LOW"]

METHODOLOGY_NOTE = (
    "Based on current POS data and identified commercial gaps. "
    "Addressable opportunity is directional and not guaranteed incremental sales."
)

DEFAULT_DATA_COVERAGE = "4 POS weeks. Price/promotion: 3 overlapping weeks."

V1_LIMITATIONS = [
    "Storytelling Engine V1 consumes Commercial Brain one-slide output only.",
    "Specialist and Commercial Brain opportunity values are not recalculated.",
    "Confidence is copied from the Commercial Brain and is never upgraded.",
    "Addressable value and addressable volume are not guaranteed incremental sales.",
    "No capture rate is introduced by the Storytelling Engine.",
    "Dashboard and PDF layers are not built in this sprint.",
]


class StorytellingStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


class HeroMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: float
    unit: str


class StoryAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    lever: str
    headline: str
    product: str
    brand: str | None = None
    retailer: str
    region: str
    addressable_value: float
    addressable_volume: float
    confidence: Confidence
    store_gap: float = 0.0
    recommended_action: str


class OneSlideStory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    headline: str
    subheadline: str
    hero_metric: HeroMetric
    hero_volume: HeroMetric
    dominant_lever: str
    key_insight: str
    retailer_insight: str
    actions: list[StoryAction] = Field(default_factory=list)
    commercial_implication: str
    methodology_note: str
    data_coverage: str
    limitations: list[str] = Field(default_factory=list)


class StorytellingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StorytellingStatus
    version: str = STORYTELLING_VERSION
    causality_claim: str = "none"
    opportunity_label: str = "Addressable commercial opportunity"
    source_brain_slide: str | None = None
    input_path: str
    one_slide: OneSlideStory
    report_output_path: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
