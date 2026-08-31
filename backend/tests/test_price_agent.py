"""End-to-end Price Agent V1 tests on canonical integrated tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.price import (
    FROZEN_V1_LIMITATIONS,
    PRICE_AGENT_VERSION,
    PriceAgentStatus,
    PriceLoadError,
    run_price,
)
from backend.agents.price.__main__ import build_parser
from backend.agents.price.models import load_price_config
from backend.tests.price_helpers import commercial_row, panel_for_product, write_commercial


def test_agent_refuses_raw_and_clean_inputs(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "upload.csv"
    write_commercial(raw, panel_for_product())
    with pytest.raises(PriceLoadError, match="canonical integrated"):
        run_price(raw, data_root=tmp_path / "data")
    clean = tmp_path / "data" / "clean" / "panel.clean.csv"
    write_commercial(clean, panel_for_product())
    with pytest.raises(PriceLoadError, match="commercial CSV"):
        run_price(clean, data_root=tmp_path / "data")


def test_agent_writes_report_and_excludes_competitors(tmp_path: Path) -> None:
    rows = panel_for_product(target_price=20.0, target_volume=50.0, peer_price=10.0, peer_volume=120.0)
    rows.append(
        commercial_row(
            manufacturer="Reckitt Benckiser",
            product="Dettol 1l",
            pos_current_price=99.0,
            sales_volume=999.0,
        )
    )
    path = write_commercial(tmp_path / "data" / "integrated" / "panel.commercial.csv", rows)
    report = run_price(path, data_root=tmp_path / "data")
    assert report.status == PriceAgentStatus.READY_WITH_WARNINGS
    assert report.version == PRICE_AGENT_VERSION
    assert report.frozen is True
    assert report.opportunity_label == "Estimated price opportunity"
    assert report.causality_claim == "none"
    assert report.manufacturer == "Unilever"
    assert report.current_period == "2026-08-16"
    assert all("Dettol" not in item.product for item in report.opportunities)
    assert (tmp_path / "data" / "price_reports" / "panel.price.json").exists()
    assert report.top_retailers
    assert report.price_signal_summary
    assert all(note in report.limitations for note in FROZEN_V1_LIMITATIONS)


def test_cli_help_mentions_directional_not_elasticity() -> None:
    help_text = build_parser().format_help()
    assert "canonical" in help_text.lower() or "integrated" in help_text.lower()
    assert "elasticity" in help_text.lower()


def test_v1_freeze_does_not_relax_confidence_or_capture_rate() -> None:
    config = load_price_config()
    assert PRICE_AGENT_VERSION == "V1"
    assert config.min_history_for_high_confidence == 8
    assert config.capture_rate == 0.25
    assert config.opportunity_label == "Estimated price opportunity"
    assert any("0.25 capture-rate" in note for note in FROZEN_V1_LIMITATIONS)
    assert any("not guaranteed incremental sales" in note.lower() for note in FROZEN_V1_LIMITATIONS)
    assert any("causal elasticity" in note.lower() for note in FROZEN_V1_LIMITATIONS)


def test_real_integrated_file_if_present() -> None:
    target = Path("backend/data/integrated/New Discovery_2026-08-27 (3).commercial.csv")
    if not target.exists():
        pytest.skip("Canonical integrated commercial dataset is not in this checkout")
    report = run_price(target, write_outputs=False)
    assert report.source_integrated_file.endswith("New Discovery_2026-08-27 (3).commercial.csv")
    assert report.manufacturer == "Unilever"
    assert report.current_period == "2026-08-16"
    assert report.status == PriceAgentStatus.READY_WITH_WARNINGS
    assert report.version == "V1"
    assert report.frozen is True
    assert report.causality_claim == "none"
    assert report.confidence_distribution.get("HIGH", 0) == 0
    assert all(note in report.limitations for note in FROZEN_V1_LIMITATIONS)
    assert "26 July" in " ".join(report.limitations) or "July" in " ".join(report.limitations)
    assert all(item.opportunity_label == "Estimated price opportunity" for item in report.top_price_opportunities)
