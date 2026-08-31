"""Deterministic Promotion Agent V1 for the canonical integrated commercial dataset.

Directional promotional insights only. Not causal incrementality.
"""

from backend.agents.promotion.agent import run_promotion
from backend.agents.promotion.loader import PromotionLoadError
from backend.agents.promotion.models import (
    PROMOTION_AGENT_VERSION,
    V1_LIMITATIONS,
    PromotionAgentStatus,
    PromotionReport,
)

__all__ = [
    "PROMOTION_AGENT_VERSION",
    "V1_LIMITATIONS",
    "PromotionAgentStatus",
    "PromotionLoadError",
    "PromotionReport",
    "run_promotion",
]
