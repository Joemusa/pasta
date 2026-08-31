"""End-to-end Promotion Agent V1 tests on canonical integrated tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.promotion import (
    PROMOTION_AGENT_VERSION,
    V1_LIMITATIONS,
    PromotionAgentStatus,
    PromotionLoadError,
    run_promotion,
)
from backend.agents.promotion.__main__ import build_parser
from backend.agents.promotion.models import load_promotion_config
from backend.tests.promo_helpers import commercial_row, promo_panel, write_commercial


def test_agent_refuses_raw_and_clean_inputs(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "upload.csv"
    write_commercial(raw, promo_panel())
    with pytest.raises(PromotionLoadError, match="canonical integrated"):
        run_promotion(raw, data_root=tmp_path / "data")
    clean = tmp_path / "data" / "clean" / "panel.clean.csv"
    write_commercial(clean, promo_panel())
    with pytest.raises(PromotionLoadError, match="commercial CSV"):
        run_promotion(clean, data_root=tmp_path / "data")


def test_agent_writes_report_and_excludes_competitors(tmp_path: Path) -> None:
    rows = promo_panel(target_promo=False, peer_promo=True, target_volume=10.0, peer_volume=20.0)
    rows.append(
        commercial_row(
            manufacturer="Reckitt Benckiser",
            product="Dettol 1l",
            pos_current_price=99.0,
            sales_volume=999.0,
            pos_percent_time_on_promo=0.0,
        )
    )
    path = write_commercial(tmp_path / "data" / "integrated" / "panel.commercial.csv", rows)
    report = run_promotion(path, data_root=tmp_path / "data")
    assert report.status == PromotionAgentStatus.READY_WITH_WARNINGS
    assert report.version == PROMOTION_AGENT_VERSION
    assert report.opportunity_label == "Estimated promotional opportunity"
    assert report.causality_claim == "none"
    assert report.manufacturer == "Unilever"
    assert report.current_period == "2026-08-16"
    assert all("Dettol" not in item.product for item in report.opportunities)
    assert (tmp_path / "data" / "promotion_reports" / "panel.promotion.json").exists()
    assert report.top_retailers
    assert report.promotion_uplift_summary
    assert all(note in report.limitations for note in V1_LIMITATIONS)


def test_cli_help_mentions_estimated_not_causal() -> None:
    help_text = build_parser().format_help()
    assert "canonical" in help_text.lower() or "integrated" in help_text.lower()
    assert "causal" in help_text.lower() or "incrementality" in help_text.lower()


def test_v1_does_not_relax_confidence_or_invent_capture_rate() -> None:
    config = load_promotion_config()
    assert PROMOTION_AGENT_VERSION == "V1"
    assert config.min_history_for_high_confidence == 8
    assert config.capture_rate == 0.25
    assert config.opportunity_label == "Estimated promotional opportunity"
    assert any("0.25 capture-rate" in note for note in V1_LIMITATIONS)
    assert any("not guaranteed incremental sales" in note.lower() for note in V1_LIMITATIONS)
    assert any("not causal incrementality" in note.lower() for note in V1_LIMITATIONS)


def test_real_integrated_file_if_present() -> None:
    target = Path("backend/data/integrated/New Discovery_2026-08-27 (3).commercial.csv")
    if not target.exists():
        pytest.skip("Canonical integrated commercial dataset is not in this checkout")
    report = run_promotion(target, write_outputs=False)
    assert report.source_integrated_file.endswith("New Discovery_2026-08-27 (3).commercial.csv")
    assert report.manufacturer == "Unilever"
    assert report.current_period == "2026-08-16"
    assert report.status in {PromotionAgentStatus.READY_WITH_WARNINGS, PromotionAgentStatus.READY}
    assert report.version == "V1"
    assert report.causality_claim == "none"
    assert report.confidence_distribution.get("HIGH", 0) == 0
    assert all(note in report.limitations for note in V1_LIMITATIONS)
    assert all(
        item.opportunity_label == "Estimated promotional opportunity" for item in report.top_promotional_opportunities
    )
    assert all(item.normal_price is None for item in report.top_promotional_opportunities)
