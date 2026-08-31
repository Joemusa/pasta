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

MACRO_CONTEXT_VERSION = "V1"

MACRO_CAUSALITY_DISCLAIMER = (
    "Macro context is supporting background only. It does not cause or recalculate POS opportunities."
)

V1_LIMITATIONS = [
    "Storytelling Engine V1 consumes Commercial Brain one-slide output only.",
    "Specialist and Commercial Brain opportunity values are not recalculated.",
    "Confidence is copied from the Commercial Brain and is never upgraded.",
    "Addressable value and addressable volume are not guaranteed incremental sales.",
    "No capture rate is introduced by the Storytelling Engine.",
    "Dashboard and PDF layers are not built in this sprint.",
    "Frozen macro context is supporting background only and is attached only when it supports the POS story.",
    "Macro HIGH confidence is the label on the frozen signal; it does not upgrade POS or Commercial Brain confidence.",
    "Macro context is not a causal explanation of POS gaps.",
    "Addressable opportunity remains not guaranteed incremental sales.",
    "Macro context does not add Price or Promotion actions or force lever variety.",
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


class MacroContextBlock(BaseModel):
    """Frozen macro pack. Supporting context only; never a second headline or a POS rescore."""

    model_config = ConfigDict(extra="forbid")

    included: bool
    role: Literal["supporting_context", "excluded", "absent"]
    version: str = MACRO_CONTEXT_VERSION
    signal: str | None = None
    evidence: str | None = None
    direction: str | None = None
    relevance: str | None = None
    supports_pos_story: bool | None = None
    commercial_implication: str | None = None
    confidence: Confidence | None = None
    sources: list[str] = Field(default_factory=list)
    supporting_line: str = ""
    causality_disclaimer: str = MACRO_CAUSALITY_DISCLAIMER
    evidence_as_of: str | None = None
    source_path: str | None = None
    exclusion_reason: str | None = None


def absent_macro_context() -> MacroContextBlock:
    return MacroContextBlock(
        included=False,
        role="absent",
        exclusion_reason="No frozen macro context pack was attached.",
    )


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
    macro_context: MacroContextBlock = Field(default_factory=absent_macro_context)


class StorytellingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StorytellingStatus
    version: str = STORYTELLING_VERSION
    causality_claim: str = "none"
    opportunity_label: str = "Addressable commercial opportunity"
    source_brain_slide: str | None = None
    source_macro_pack: str | None = None
    input_path: str
    one_slide: OneSlideStory
    report_output_path: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
