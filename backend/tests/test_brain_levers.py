"""Dominant lever rules, double-counting, scoring, and ingestion."""

from __future__ import annotations

from pathlib import Path

from backend.agents.brain.levers import decide_all, decide_lever
from backend.agents.brain.loader import DistSignal, PriceSignal, PromoSignal, discover_bundle
from backend.agents.brain.models import BrainConfig, DominantLever, load_brain_config
from backend.agents.brain.scoring import evidence_factor, opportunity_score, priority_score
from backend.tests.brain_helpers import dist_opp, price_opp, promo_opp, write_bundle


def _dist(**kwargs: object) -> DistSignal:
    row = dist_opp(**kwargs)  # type: ignore[arg-type]
    return DistSignal(
        product=str(row["sku"]),
        retailer=str(row["retailer"]),
        region=str(row["region"]),
        value=float(row["value_opportunity"]),
        volume=float(row["volume_opportunity"]),
        confidence=str(row["confidence"]),
        current_stores=float(row["current_stores"]),
        benchmark_stores=float(row["benchmark_stores"]),
        store_gap=float(row["store_gap"]),
        value_per_store=float(row["value_per_store"]),
        volume_per_store=float(row["volume_per_store"]),
        outlier_flags=[],
    )


def _price(**kwargs: object) -> PriceSignal:
    row = price_opp(**kwargs)  # type: ignore[arg-type]
    return PriceSignal(
        product=str(row["product"]),
        brand="Handy Andy",
        retailer=str(row["retailer"]),
        region=str(row["region"]),
        value=float(row["estimated_value_opportunity"]),
        volume=float(row["estimated_volume_opportunity"]),
        confidence=str(row["confidence"]),
        recommendation=str(row["recommendation"]),
        price_signal=str(row["price_signal"]),
        current_price=20.0,
        benchmark_price=10.0,
        distribution_primary_lever=bool(row["distribution_primary_lever"]),
        mixed_promotion_comparison=False,
        outlier_flags=[],
    )


def _promo(**kwargs: object) -> PromoSignal:
    row = promo_opp(**kwargs)  # type: ignore[arg-type]
    return PromoSignal(
        product=str(row["product"]),
        brand="Handy Andy",
        retailer=str(row["retailer"]),
        region=str(row["region"]),
        value=float(row["estimated_incremental_value"]),
        volume=float(row["estimated_incremental_volume"]),
        confidence=str(row["confidence"]),
        recommendation=str(row["recommendation"]),
        volume_uplift_pct=float(row["volume_uplift_pct"]),
        distribution_primary_lever=bool(row["distribution_primary_lever"]),
        subsidising_existing_demand=bool(row["subsidising_existing_demand"]),
        mixed_promotion_window=False,
        outlier_flags=[],
    )


def test_distribution_first_beats_price_and_is_not_summed() -> None:
    config = BrainConfig()
    decision = decide_lever(
        dist=_dist(value_opportunity=800.0, volume_opportunity=80.0),
        price=_price(value=500.0, volume=25.0),
        promo=None,
        commercial=None,
        config=config,
    )
    assert decision.dominant == DominantLever.DISTRIBUTION
    assert decision.primary_value == 800.0
    assert decision.primary_volume == 80.0
    assert decision.gross_value == 1300.0
    assert decision.primary_value != decision.gross_value
    assert any("not added" in note.lower() or "not summed" in note.lower() for note in decision.limitations)


def test_promotion_rule_when_distribution_is_adequate() -> None:
    config = BrainConfig()
    decision = decide_lever(
        dist=None,
        price=_price(value=200.0, volume=10.0),
        promo=_promo(value=400.0, volume=20.0, uplift=0.4),
        commercial=None,
        config=config,
    )
    assert decision.dominant == DominantLever.PROMOTION
    assert decision.primary_value == 400.0
    assert decision.primary_value != decision.gross_value


def test_price_rule_when_promo_does_not_explain() -> None:
    config = BrainConfig()
    decision = decide_lever(
        dist=None,
        price=_price(value=500.0, volume=20.0),
        promo=_promo(recommendation="DO NOT PROMOTE", value=0.0, volume=0.0, uplift=-0.2),
        commercial=None,
        config=config,
    )
    assert decision.dominant == DominantLever.PRICE
    assert decision.primary_value == 500.0


def test_multi_lever_only_when_complementary() -> None:
    config = BrainConfig()
    complementary = decide_lever(
        dist=_dist(),
        price=None,
        promo=_promo(value=300.0, distribution_primary_lever=False, uplift=0.4),
        commercial=None,
        config=config,
    )
    assert complementary.dominant == DominantLever.MULTI_LEVER
    assert complementary.primary_value == 640.0
    assert complementary.secondary_value == 300.0
    flagged = decide_lever(
        dist=_dist(),
        price=None,
        promo=_promo(value=300.0, distribution_primary_lever=True, uplift=0.4),
        commercial=None,
        config=config,
    )
    assert flagged.dominant == DominantLever.DISTRIBUTION


def test_architecture_review_is_not_a_price_lever() -> None:
    config = BrainConfig()
    decision = decide_lever(
        dist=None,
        price=_price(recommendation="PRICE ARCHITECTURE REVIEW", value=0.0, volume=0.0),
        promo=None,
        commercial=None,
        config=config,
    )
    assert decision.dominant == DominantLever.INSUFFICIENT_EVIDENCE


def test_low_confidence_does_not_outrank_high_on_size_alone() -> None:
    config = BrainConfig()
    huge_low = decide_lever(
        dist=None,
        price=None,
        promo=_promo(value=20000.0, volume=400.0),
        commercial=None,
        config=config,
    )
    small_high = decide_lever(
        dist=_dist(value_opportunity=5000.0, volume_opportunity=50.0, confidence="HIGH"),
        price=None,
        promo=None,
        commercial=None,
        config=config,
    )
    huge_low.confidence = "LOW"
    assert evidence_factor("LOW", config) < evidence_factor("HIGH", config)
    assert priority_score(small_high, config) > priority_score(huge_low, config)
    assert opportunity_score(20000.0, config) > opportunity_score(5000.0, config)


def test_price_selected_when_promo_is_weaker() -> None:
    config = BrainConfig()
    decision = decide_lever(
        dist=None,
        price=_price(value=500.0, volume=20.0),
        promo=_promo(value=100.0, volume=5.0, uplift=0.4),
        commercial=None,
        config=config,
    )
    assert decision.dominant == DominantLever.PRICE
    assert decision.primary_value == 500.0
    assert decision.secondary == DominantLever.PROMOTION


def test_subsidising_promo_is_not_a_primary_lever() -> None:
    config = BrainConfig()
    decision = decide_lever(
        dist=None,
        price=None,
        promo=_promo(value=400.0, volume=20.0, uplift=0.4, subsidising=True),
        commercial=None,
        config=config,
    )
    assert decision.dominant == DominantLever.INSUFFICIENT_EVIDENCE
    assert decision.primary_value == 0.0


def test_discover_bundle_reads_specialist_json(tmp_path: Path) -> None:
    root = write_bundle(tmp_path, dist=[dist_opp()], price=[price_opp()], promo=[promo_opp()])
    bundle = discover_bundle(root)
    assert len(bundle.dist) == 1
    assert len(bundle.price) == 1
    assert len(bundle.promo) == 1
    assert bundle.current_period == "2026-08-16"


def test_decide_all_joins_on_grain() -> None:
    config = BrainConfig()
    decisions = decide_all(
        dist=[_dist(region="Gauteng"), _dist(region="Western Cape")],
        price=[_price(region="Gauteng")],
        promo=[],
        commercial={},
        config=config,
    )
    assert len(decisions) == 2
    gauteng = next(item for item in decisions if item.region == "Gauteng")
    assert gauteng.overlap is True
    assert gauteng.specialist_count == 2


def test_config_weights_are_loaded() -> None:
    config = load_brain_config()
    assert config.n_actions == 3
    assert config.evidence_low < config.evidence_high
    assert config.value_reference == 10000.0
    assert "Non-sa" in config.excluded_action_regions
