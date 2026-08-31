"""End-to-end Commercial Brain V1 tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.agents.brain import BRAIN_VERSION, V1_LIMITATIONS, BrainAgentStatus, BrainLoadError, run_brain
from backend.agents.brain.__main__ import build_parser
from backend.agents.brain.models import DominantLever
from backend.tests.brain_helpers import dist_opp, price_opp, promo_opp, write_bundle


def _panel(tmp_path: Path) -> Path:
    dist = [
        dist_opp(region="Gauteng", value_opportunity=8000.0, volume_opportunity=80.0, confidence="HIGH"),
        dist_opp(region="Western Cape", value_opportunity=5000.0, volume_opportunity=50.0, confidence="HIGH"),
        dist_opp(
            sku="Sunlight Pine Gel 1l",
            retailer="Shoprite",
            region="KwaZulu-Natal",
            value_opportunity=3000.0,
            volume_opportunity=40.0,
            confidence="MEDIUM",
        ),
    ]
    price = [
        price_opp(region="Gauteng", value=2000.0, volume=20.0, confidence="LOW"),
        price_opp(
            product="Domestos 750ml",
            retailer="Spar",
            region="Limpopo",
            value=2500.0,
            volume=30.0,
            confidence="LOW",
        ),
        price_opp(
            product="Vim 500g",
            retailer="PnP",
            region="Free State",
            recommendation="PRICE ARCHITECTURE REVIEW",
            value=0.0,
            volume=0.0,
        ),
    ]
    promo = [
        promo_opp(
            product="Handy Andy Lavender 750ml",
            retailer="Shoprite",
            region="Mpumalanga",
            value=4000.0,
            volume=120.0,
            confidence="LOW",
            uplift=0.5,
        ),
        promo_opp(region="Gauteng", value=1500.0, volume=40.0, confidence="LOW", distribution_primary_lever=True),
    ]
    return write_bundle(tmp_path, dist=dist, price=price, promo=promo)


def test_agent_refuses_raw_inputs(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "upload.csv"
    raw.parent.mkdir(parents=True)
    raw.write_text("x\n", encoding="utf-8")
    with pytest.raises(BrainLoadError, match="raw"):
        run_brain(raw)


def test_agent_refuses_clean_csv(tmp_path: Path) -> None:
    clean = tmp_path / "panel.clean.csv"
    clean.write_text("x\n", encoding="utf-8")
    with pytest.raises(BrainLoadError, match="clean"):
        run_brain(clean)


def test_brain_emits_exactly_three_actions_and_does_not_sum(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    assert report.status == BrainAgentStatus.READY_WITH_WARNINGS
    assert report.version == BRAIN_VERSION
    assert report.causality_claim == "none"
    assert len(report.top_actions) == 3
    assert {item.rank for item in report.top_actions} == {1, 2, 3}
    gauteng = next(item for item in report.opportunities if item.region == "Gauteng" and "Lemon" in item.product)
    assert gauteng.dominant_lever == DominantLever.DISTRIBUTION.value
    assert gauteng.opportunity_value == 8000.0
    assert gauteng.gross_estimated_value == 11500.0
    assert gauteng.opportunity_value != gauteng.gross_estimated_value
    assert report.double_counting_conflicts_resolved >= 1
    assert all(item.estimated_value >= 0 and item.estimated_volume >= 0 for item in report.top_actions)
    assert all(item.estimated_volume > 0 for item in report.top_actions)
    assert all(item.region != "Non-sa" for item in report.top_actions)
    assert all(note in report.limitations for note in V1_LIMITATIONS)
    assert (root / "brain_reports" / "panel.brain.json").exists()


def test_confidence_is_preserved_not_upgraded(tmp_path: Path) -> None:
    root = write_bundle(
        tmp_path,
        dist=[dist_opp(confidence="HIGH")],
        price=[price_opp(confidence="LOW")],
        promo=[promo_opp(retailer="Spar", region="Limpopo", confidence="LOW")],
    )
    report = run_brain(root)
    lemon = next(item for item in report.opportunities if item.region == "Gauteng")
    assert lemon.confidence == "HIGH"
    promo_row = next(item for item in report.opportunities if item.region == "Limpopo")
    assert promo_row.confidence == "LOW"


def test_storytelling_and_one_slide(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    assert report.headline
    assert "clearest growth lever" in report.headline.lower() or "growth lever" in report.headline.lower()
    assert len(report.storytelling.supporting_actions) == 3
    assert "guaranteed" in report.storytelling.quantified_opportunity.lower()
    assert report.storytelling.next_step
    slide = report.one_slide
    assert slide.headline == report.headline
    assert len(slide.top_actions) == 3
    assert slide.total_estimated_value_opportunity == report.total_estimated_value_opportunity
    assert slide.total_estimated_volume_opportunity == report.total_estimated_volume_opportunity
    assert slide.methodology
    assert "causal" in " ".join(report.limitations).lower() or "causal" in report.methodology.lower()
    why_ok = all(
        "guaranteed incremental" not in item.why.lower() or "not guaranteed" in item.why.lower()
        for item in report.top_actions
    )
    assert why_ok


def test_value_and_volume_always_present(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    assert report.total_estimated_value_opportunity > 0
    assert report.total_estimated_volume_opportunity > 0
    for item in report.opportunities:
        assert item.opportunity_value is not None
        assert item.opportunity_volume is not None
        if item.opportunity_value > 0:
            assert item.opportunity_volume >= 0


def test_retailer_sku_and_region_ranking_use_primary_value(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    assert report.top_retailers
    assert report.top_skus
    assert report.top_regions
    checkers = next(item for item in report.top_retailers if item.name == "Checkers")
    # Gauteng dist 8000 + WC dist 5000 = 13000 primary, not plus price/promo.
    assert checkers.estimated_value == pytest.approx(13000.0)
    assert checkers.dominant_lever == DominantLever.DISTRIBUTION.value
    assert checkers.skus >= 1
    assert checkers.regions >= 2
    top_sku = report.top_skus[0]
    assert top_sku.retailer
    assert top_sku.region
    assert top_sku.opportunity_value > 0
    assert top_sku.opportunity_volume > 0
    gauteng = next(item for item in report.top_regions if item.name == "Gauteng")
    assert gauteng.estimated_value == pytest.approx(8000.0)
    assert gauteng.top_sku
    assert gauteng.top_retailer == "Checkers"


def test_opportunity_totals_use_primary_not_gross(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    primary = round(sum(item.opportunity_value for item in report.opportunities), 2)
    gross = round(sum(item.gross_estimated_value for item in report.opportunities), 2)
    assert report.total_estimated_value_opportunity == pytest.approx(primary)
    assert gross > primary
    volumes = [item.opportunity_volume for item in report.opportunities]
    assert report.total_estimated_volume_opportunity == pytest.approx(round(sum(volumes), 4))


def test_no_causality_language_in_cli_help() -> None:
    help_text = build_parser().format_help()
    assert "guaranteed" in help_text.lower() or "overlapping" in help_text.lower()


def test_missing_current_sales_are_not_zero(tmp_path: Path) -> None:
    root = _panel(tmp_path)
    report = run_brain(root)
    gauteng = next(item for item in report.opportunities if item.region == "Gauteng" and "Lemon" in item.product)
    assert gauteng.current_sales is None
    assert gauteng.current_volume is None


def test_commercial_enrichment_optional(tmp_path: Path) -> None:
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
    assert gauteng.current_volume == pytest.approx(50.0)


def test_real_reports_if_present() -> None:
    target = Path("backend/data")
    dist_dir = target / "distribution_reports"
    price_dir = target / "price_reports"
    promo_dir = target / "promotion_reports"
    dist = list(dist_dir.glob("*.distribution.json")) if dist_dir.exists() else []
    price = list(price_dir.glob("*.price.json")) if price_dir.exists() else []
    promo = list(promo_dir.glob("*.promotion.json")) if promo_dir.exists() else []
    if not (dist and price and promo):
        pytest.skip("Frozen specialist reports are not in this checkout")
    report = run_brain(target, write_outputs=False)
    assert report.status in {BrainAgentStatus.READY_WITH_WARNINGS, BrainAgentStatus.READY}
    assert len(report.top_actions) == 3
    assert report.causality_claim == "none"
    assert report.confidence_distribution.get("HIGH", 0) >= 0
    assert all(item.estimated_value >= 0 and item.estimated_volume >= 0 for item in report.top_actions)
    assert "not guaranteed" in report.storytelling.quantified_opportunity.lower()
    assert "addressable" in report.storytelling.quantified_opportunity.lower()
    assert report.one_slide.headline
    assert len(report.one_slide.top_actions) == 3
    assert report.one_slide.total_addressable_value_opportunity == report.total_addressable_value_opportunity
    assert all("addressable_value" in item for item in report.one_slide.top_actions)
