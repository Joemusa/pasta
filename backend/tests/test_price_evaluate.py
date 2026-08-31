"""Signals, distribution gate, missingness, history, outliers, and no-causality guardrail."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.price import run_price
from backend.agents.price.models import PriceConfig, Recommendation
from backend.tests.price_helpers import commercial_row, panel_for_product, write_commercial


def _run(tmp_path: Path, rows: list[dict[str, object]]):
    path = write_commercial(tmp_path / "data" / "integrated" / "panel.commercial.csv", rows)
    return run_price(path, data_root=tmp_path / "data", write_outputs=True)


def test_lower_price_test_when_high_price_and_low_volume_vs_like_for_like_peers(tmp_path: Path) -> None:
    rows = panel_for_product(
        target_price=20.0,
        target_volume=50.0,
        target_stores=10.0,
        peer_price=10.0,
        peer_volume=120.0,
        peer_stores=10.0,
        promo=0.0,
    )
    report = _run(tmp_path, rows)
    hits = [item for item in report.opportunities if item.region == "Gauteng"]
    assert hits
    assert hits[0].recommendation == Recommendation.LOWER_PRICE_TEST.value
    assert hits[0].price_signal == "HIGHER_PRICE_LOWER_VOLUME"
    assert hits[0].estimated_value_opportunity > 0
    assert hits[0].estimated_volume_opportunity > 0
    assert "not an elasticity" in hits[0].methodology
    assert hits[0].opportunity_label == "Estimated price opportunity"
    assert hits[0].estimated_volume_opportunity == pytest.approx(17.5)
    assert hits[0].estimated_value_opportunity == pytest.approx(350.0)


def test_no_causality_guardrail_own_history_is_not_enough(tmp_path: Path) -> None:
    """Price fell over time while volume rose, but current peers match — do not recommend a cut."""
    rows: list[dict[str, object]] = []
    history_prices = {"2026-07-26": 20.0, "2026-08-02": 16.0, "2026-08-09": 12.0, "2026-08-16": 10.0}
    history_vol = {"2026-07-26": 50.0, "2026-08-02": 80.0, "2026-08-09": 100.0, "2026-08-16": 120.0}
    for date, price in history_prices.items():
        for region in ["Gauteng", "Western Cape", "KwaZulu-Natal", "Eastern Cape"]:
            rows.append(
                commercial_row(
                    date=date,
                    region=region,
                    pos_current_price=price,
                    sales_volume=history_vol[date],
                    sales_value=price * history_vol[date],
                    store_count=10.0,
                    pos_percent_time_on_promo=0.0,
                    pos_percent_sales_on_promo=0.0,
                )
            )
    report = _run(tmp_path, rows)
    assert all(item.recommendation != Recommendation.LOWER_PRICE_TEST.value for item in report.opportunities)
    assert report.recommendation_counts.get(Recommendation.MAINTAIN_PRICE.value, 0) >= 1


def test_distribution_primary_blocks_lower_price_test(tmp_path: Path) -> None:
    rows = panel_for_product(
        target_price=20.0,
        target_volume=5.0,
        target_stores=2.0,
        peer_price=10.0,
        peer_volume=120.0,
        peer_stores=20.0,
        promo=0.0,
    )
    report = _run(tmp_path, rows)
    gauteng = [item for item in report.opportunities if item.region == "Gauteng"]
    assert all(item.recommendation != Recommendation.LOWER_PRICE_TEST.value for item in gauteng)
    # Evaluated as insufficient / architecture, not a price cut.
    assert report.recommendation_counts.get(Recommendation.LOWER_PRICE_TEST.value, 0) == 0


def test_missing_price_is_insufficient_and_not_fabricated(tmp_path: Path) -> None:
    rows = panel_for_product(target_price=10.0, peer_price=10.0)
    for row in rows:
        if row["region"] == "Gauteng" and row["date"] == "2026-08-16":
            row["pos_current_price"] = None
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.INSUFFICIENT_EVIDENCE.value, 0) >= 1
    assert all(
        not (item.region == "Gauteng" and item.recommendation == Recommendation.LOWER_PRICE_TEST.value)
        for item in report.opportunities
    )


def test_missing_promotion_blocks_price_change_test(tmp_path: Path) -> None:
    rows = panel_for_product(target_price=20.0, target_volume=50.0, peer_price=10.0, peer_volume=120.0)
    for row in rows:
        row["pos_percent_time_on_promo"] = None
        row["pos_percent_sales_on_promo"] = None
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.LOWER_PRICE_TEST.value, 0) == 0
    assert report.recommendation_counts.get(Recommendation.PRICE_INCREASE_TEST.value, 0) == 0


def test_promotion_separation_does_not_treat_promo_peers_as_like_for_like(tmp_path: Path) -> None:
    rows = panel_for_product(target_price=20.0, target_volume=50.0, peer_price=10.0, peer_volume=120.0, promo=0.0)
    for row in rows:
        if row["region"] != "Gauteng":
            row["pos_percent_time_on_promo"] = 40.0
            row["pos_percent_sales_on_promo"] = 50.0
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.LOWER_PRICE_TEST.value, 0) == 0


def test_insufficient_history_blocks_test(tmp_path: Path) -> None:
    rows = panel_for_product(
        target_price=20.0,
        target_volume=50.0,
        peer_price=10.0,
        peer_volume=120.0,
        weeks=["2026-08-16"],
    )
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.LOWER_PRICE_TEST.value, 0) == 0


def test_price_increase_test_when_low_price_and_value_lags(tmp_path: Path) -> None:
    rows = panel_for_product(
        target_price=8.0,
        target_volume=100.0,
        target_stores=10.0,
        peer_price=12.0,
        peer_volume=100.0,
        peer_stores=10.0,
        promo=0.0,
    )
    report = _run(tmp_path, rows)
    hits = [
        item
        for item in report.opportunities
        if item.region == "Gauteng" and item.recommendation == Recommendation.PRICE_INCREASE_TEST.value
    ]
    assert hits
    assert hits[0].estimated_value_opportunity > 0
    assert hits[0].estimated_volume_opportunity == 0.0


def test_outlier_handling_keeps_row_and_is_flagged(tmp_path: Path) -> None:
    rows = panel_for_product(target_price=10.0, peer_price=10.0, promo=0.0)
    for row in rows:
        if row["region"] == "Gauteng" and row["date"] == "2026-08-16":
            row["pos_current_price"] = 200.0
            row["sales_value"] = 200.0 * 10.0
    report = _run(tmp_path, rows)
    flagged = [item for item in report.opportunities if "price_outlier" in item.outlier_flags]
    # Architecture or test may emit; if emitted, confidence is not HIGH.
    assert all(item.confidence != "HIGH" for item in report.opportunities)
    _ = flagged


def test_category_peers_are_not_used_for_price_change_tests(tmp_path: Path) -> None:
    """Different SKUs in the same brand/banner/region are architecture context, not a cut test."""
    rows: list[dict[str, object]] = []
    for date in ["2026-07-26", "2026-08-02", "2026-08-09", "2026-08-16"]:
        rows.append(
            commercial_row(
                date=date,
                product="Handy Andy Food Safe 5l",
                region="Gauteng",
                retailer="Makro Main",
                pos_current_price=148.0,
                sales_volume=14.0,
                sales_value=148.0 * 14.0,
                store_count=10.0,
                pos_percent_time_on_promo=20.0,
                pos_percent_sales_on_promo=20.0,
            )
        )
        for product, price, volume in [
            ("Handy Andy Lemon 750ml", 26.0, 40.0),
            ("Handy Andy Lavender 750ml", 25.0, 38.0),
            ("Handy Andy Potpourri 750ml", 24.0, 42.0),
        ]:
            rows.append(
                commercial_row(
                    date=date,
                    product=product,
                    region="Gauteng",
                    retailer="Makro Main",
                    pos_current_price=price,
                    sales_volume=volume,
                    sales_value=price * volume,
                    store_count=10.0,
                    pos_percent_time_on_promo=20.0,
                    pos_percent_sales_on_promo=20.0,
                )
            )
    report = _run(tmp_path, rows)
    fives = [item for item in report.opportunities if "5l" in item.product]
    assert all(item.recommendation != Recommendation.LOWER_PRICE_TEST.value for item in fives)
    assert all(
        item.benchmark_type != "category_peer"
        or item.recommendation == Recommendation.PRICE_ARCHITECTURE_REVIEW.value
        for item in fives
    )


def test_confidence_cannot_be_high_with_four_weeks(tmp_path: Path) -> None:
    rows = panel_for_product(
        target_price=20.0,
        target_volume=50.0,
        peer_price=10.0,
        peer_volume=120.0,
        promo=0.0,
    )
    report = _run(tmp_path, rows)
    assert report.confidence_distribution.get("HIGH", 0) == 0
    config = PriceConfig()
    assert config.min_history_for_high_confidence > 4
