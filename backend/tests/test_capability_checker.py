from __future__ import annotations

from backend.agents.data_qa.capability_checker import analysis_ready, check_capabilities
from backend.agents.data_qa.models import load_qa_config
from backend.tests.helpers import canonical_rows


def test_full_history_enables_price_promo_and_distribution() -> None:
    frame = canonical_rows(n_months=12)
    ready = analysis_ready(frame, has_critical_blocker=False)
    caps = check_capabilities(frame, load_qa_config(), ready=ready)
    assert ready is True
    assert caps.distribution is True
    assert caps.price is True
    assert caps.promotion is True
    assert caps.macro_overlay is True
    assert caps.social_evidence is True
    assert caps.commercial_brain is True


def test_short_history_blocks_price_and_promotion_agents() -> None:
    frame = canonical_rows(n_months=3)
    caps = check_capabilities(frame, load_qa_config(), ready=True)
    assert caps.price is False
    assert caps.promotion is False
    assert caps.distribution is True
    assert caps.commercial_brain is True
