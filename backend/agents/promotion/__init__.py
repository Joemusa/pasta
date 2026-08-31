"""Deterministic Promotion Agent V1 for the canonical integrated commercial dataset.

V1 is frozen: estimated promotional opportunity only. HIGH confidence still requires 8+ weeks.
"""

from backend.agents.promotion.agent import run_promotion
from backend.agents.promotion.loader import PromotionLoadError
from backend.agents.promotion.models import (
    FROZEN_V1_LIMITATIONS,
    PROMOTION_AGENT_VERSION,
    V1_LIMITATIONS,
    PromotionAgentStatus,
    PromotionReport,
)

__all__ = [
    "FROZEN_V1_LIMITATIONS",
    "PROMOTION_AGENT_VERSION",
    "V1_LIMITATIONS",
    "PromotionAgentStatus",
    "PromotionLoadError",
    "PromotionReport",
    "run_promotion",
]
