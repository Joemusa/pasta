"""Transparent Commercial Priority Score. LOW-confidence size does not automatically win."""

from __future__ import annotations

import math

from backend.agents.brain.levers import LeverDecision
from backend.agents.brain.models import BrainConfig, DominantLever

METHODOLOGY = (
    "Commercial Priority Score = opportunity_score * evidence_factor * actionability_factor "
    "* data_quality_factor. opportunity_score = log1p(primary_lever_value) / log1p(value_reference). "
    "evidence_factor maps specialist confidence of the primary lever (HIGH/MEDIUM/LOW) and is never "
    "upgraded. actionability_factor is lower for MULTI-LEVER than for a single clear lever. "
    "data_quality_factor starts at 1.0 and is reduced for outlier flags and mixed promotion windows. "
    "The score uses primary-lever value only; gross specialist values are not summed. "
    "Estimates remain directional and are not guaranteed incremental sales."
)


def evidence_factor(confidence: str, config: BrainConfig) -> float:
    if confidence == "HIGH":
        return config.evidence_high
    if confidence == "MEDIUM":
        return config.evidence_medium
    return config.evidence_low


def actionability_factor(decision: LeverDecision, config: BrainConfig) -> float:
    if decision.dominant == DominantLever.INSUFFICIENT_EVIDENCE:
        return config.actionability_insufficient
    if decision.dominant == DominantLever.MULTI_LEVER:
        return config.actionability_multi
    return config.actionability_single


def data_quality_factor(decision: LeverDecision, config: BrainConfig) -> float:
    factor = config.data_quality_base
    flags: list[str] = []
    if decision.dist is not None:
        flags.extend(decision.dist.outlier_flags)
    if decision.price is not None:
        flags.extend(decision.price.outlier_flags)
        if decision.price.mixed_promotion_comparison:
            factor -= config.mixed_promo_penalty
    if decision.promo is not None:
        flags.extend(decision.promo.outlier_flags)
        if decision.promo.mixed_promotion_window:
            factor -= config.mixed_promo_penalty
    if flags:
        factor -= config.outlier_penalty
    return max(0.0, factor)


def opportunity_score(primary_value: float, config: BrainConfig) -> float:
    if primary_value <= 0 or config.value_reference <= 0:
        return 0.0
    return math.log1p(primary_value) / math.log1p(config.value_reference)


def priority_score(decision: LeverDecision, config: BrainConfig) -> float:
    score = (
        opportunity_score(decision.primary_value, config)
        * evidence_factor(decision.confidence, config)
        * actionability_factor(decision, config)
        * data_quality_factor(decision, config)
    )
    return round(score, 6)
