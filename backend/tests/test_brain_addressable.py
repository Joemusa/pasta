"""Addressable-value terminology and reporting for Commercial Brain V1."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.agents.brain.addressable import (
    ADDRESSABLE_METHODOLOGY,
    distribution_addressable_value,
    distribution_addressable_volume,
)
from backend.agents.brain.agent import run_brain
from backend.tests.brain_helpers import dist_opp, price_opp, write_bundle
from backend.tests.test_brain_agent import _panel


def test_distribution_addressable_value_is_value_per_store_times_gap() -> None:
    assert distribution_addressable_value(80.0, 8.0) == pytest.approx(640.0)
    assert distribution_addressable_value(188.93, 24.0) == pytest.approx(4534.32)


def test_distribution_addressable_volume_is_volume_per_store_times_gap() -> None:
    assert distribution_addressable_volume(8.0, 8.0) == pytest.approx(64.0)
    assert distribution_addressable_volume(10.65, 6.0) == pytest.approx(63.9)


def test_brain_reports_addressable_fields_from_specialist_not_rescore(tmp_path: Path) -> None:
    root = write_bundle(tmp_path, dist=[dist_opp()], price=[price_opp(value=0.0, volume=0.0)], promo=[])
    report = run_brain(root)
    row = next(item for item in report.opportunities if item.region == "Gauteng")
    assert row.addressable_value_opportunity == pytest.approx(640.0)
    assert row.addressable_volume_opportunity == pytest.approx(64.0)
    assert row.distribution_addressable_value == pytest.approx(640.0)
    assert row.distribution_addressable_volume == pytest.approx(64.0)
    assert row.opportunity_value == row.addressable_value_opportunity
    assert row.distribution_addressable_value == distribution_addressable_value(80.0, 8.0)
    assert row.distribution_addressable_volume == distribution_addressable_volume(8.0, 8.0)


def test_current_sales_never_confused_with_opportunity(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    integrated = root / "integrated"
    integrated.mkdir()
    pd.DataFrame(
        [
            {
                "product": "Handy Andy Lemon 750ml",
                "manufacturer": "Unilever",
                "brand": "Handy Andy",
                "retailer": "Checkers",
                "region": "Gauteng",
                "date": "2026-08-16",
                "sales_value": 999.0,
                "sales_volume": 50.0,
                "store_count": 4.0,
                "in_pos": True,
            }
        ]
    ).to_csv(integrated / "panel.commercial.csv", index=False)
    report = run_brain(root)
    gauteng = next(item for item in report.opportunities if item.region == "Gauteng" and "Lemon" in item.product)
    assert gauteng.current_sales == pytest.approx(999.0)
    assert gauteng.addressable_value_opportunity == pytest.approx(8000.0)
    assert gauteng.current_sales != gauteng.addressable_value_opportunity
    assert "current sales" in " ".join(gauteng.evidence).lower()
    assert "not the opportunity" in " ".join(gauteng.evidence).lower()
    assert all(item.current_sales != item.addressable_value for item in report.top_actions if item.current_sales)


def test_opportunity_never_described_as_guaranteed_incremental_sales(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    blob = " ".join(
        [
            report.headline,
            report.storytelling.quantified_opportunity,
            report.storytelling.next_step,
            report.methodology,
            " ".join(report.limitations),
            " ".join(report.risks),
            " ".join(item.why for item in report.top_actions),
            " ".join(" ".join(item.evidence) for item in report.top_actions),
        ]
    ).lower()
    assert "not guaranteed incremental sales" in blob
    assert "addressable value" in blob
    assert "addressable volume" in blob
    assert "clearest growth lever" in report.headline.lower()
    assert "value_per_store" in ADDRESSABLE_METHODOLOGY
    assert "distribution_store_gap" in ADDRESSABLE_METHODOLOGY
    assert "capture rate" not in report.headline.lower()
    slide = report.one_slide
    for action in slide.top_actions:
        assert "addressable_value" in action
        assert "addressable_volume" in action
        assert action["addressable_value"] == action["estimated_value"]
        assert "not guaranteed incremental sales" in action["why"].lower()
        assert "guaranteed incremental sales" in action["why"].lower()


def test_addressable_totals_alias_estimated_and_three_actions_remain(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    assert len(report.top_actions) == 3
    assert report.total_addressable_value_opportunity == report.total_estimated_value_opportunity
    assert report.total_addressable_volume_opportunity == report.total_estimated_volume_opportunity
    assert report.one_slide.total_addressable_value_opportunity == report.total_addressable_value_opportunity
    gauteng = next(item for item in report.opportunities if item.region == "Gauteng" and "Lemon" in item.product)
    assert gauteng.addressable_value_opportunity != gauteng.gross_estimated_value
    assert report.double_counting_conflicts_resolved >= 1
    lemon = next(item for item in report.opportunities if item.region == "Gauteng")
    assert lemon.confidence == "HIGH"
