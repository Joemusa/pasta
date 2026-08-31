"""Overlap flags for Price and Distribution opportunities. Not combined."""

from __future__ import annotations

import json
from pathlib import Path

from backend.agents.promotion import run_promotion
from backend.agents.promotion.models import PrimaryLever, Recommendation
from backend.agents.promotion.overlap import load_overlap_index
from backend.tests.promo_helpers import promo_panel, write_commercial


def test_price_overlap_is_flagged_and_not_combined(tmp_path: Path) -> None:
    rows = promo_panel(target_promo=False, peer_promo=True, target_volume=10.0, peer_volume=20.0)
    path = write_commercial(tmp_path / "data" / "integrated" / "panel.commercial.csv", rows)
    price_dir = tmp_path / "data" / "price_reports"
    price_dir.mkdir(parents=True)
    price_dir.joinpath("panel.price.json").write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "product": "Handy Andy Lemon 750ml",
                        "retailer": "Checkers",
                        "region": "Gauteng",
                        "recommendation": "LOWER PRICE TEST",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = run_promotion(path, data_root=tmp_path / "data")
    hits = [item for item in report.opportunities if item.region == "Gauteng"]
    assert hits
    assert hits[0].overlaps_price_opportunity is True
    assert hits[0].primary_lever in {PrimaryLever.OVERLAP.value, PrimaryLever.PROMOTION.value}
    assert "not combined" in " ".join(hits[0].limitations).lower() or "Price Agent" in " ".join(hits[0].limitations)


def test_distribution_overlap_is_flagged(tmp_path: Path) -> None:
    rows = promo_panel(target_promo=False, peer_promo=True, target_volume=10.0, peer_volume=20.0)
    path = write_commercial(tmp_path / "data" / "integrated" / "panel.commercial.csv", rows)
    dist_dir = tmp_path / "data" / "distribution_reports"
    dist_dir.mkdir(parents=True)
    dist_dir.joinpath("panel.distribution.json").write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "sku": "Handy Andy Lemon 750ml",
                        "retailer": "Checkers",
                        "region": "Gauteng",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = run_promotion(path, data_root=tmp_path / "data")
    hits = [item for item in report.opportunities if item.region == "Gauteng"]
    assert hits
    assert hits[0].overlaps_distribution_opportunity is True


def test_overlap_index_reads_persisted_reports(tmp_path: Path) -> None:
    (tmp_path / "price_reports").mkdir()
    (tmp_path / "distribution_reports").mkdir()
    (tmp_path / "price_reports" / "demo.price.json").write_text(
        json.dumps({"opportunities": [{"product": "A", "retailer": "R", "region": "G", "recommendation": "X"}]}),
        encoding="utf-8",
    )
    (tmp_path / "distribution_reports" / "demo.distribution.json").write_text(
        json.dumps({"opportunities": [{"sku": "A", "retailer": "R", "region": "G"}]}),
        encoding="utf-8",
    )
    index = load_overlap_index(tmp_path, "demo")
    assert index.has_price("A", "R", "G")
    assert index.has_distribution("A", "R", "G")
    assert index.price_recommendation("A", "R", "G") == "X"


def test_double_count_control_keeps_separate_opportunity_lists(tmp_path: Path) -> None:
    rows = promo_panel(target_promo=False, peer_promo=True, target_volume=10.0, peer_volume=20.0)
    path = write_commercial(tmp_path / "data" / "integrated" / "panel.commercial.csv", rows)
    report = run_promotion(path, data_root=tmp_path / "data")
    assert report.opportunities
    assert all(item.opportunity_label == "Estimated promotional opportunity" for item in report.opportunities)
    assert report.causality_claim == "none"
    assert Recommendation.PROMOTE.value in report.recommendation_counts
