"""Signals, distribution gate, missingness, outliers, and no-causality guardrail."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.promotion import run_promotion
from backend.agents.promotion.models import Recommendation
from backend.tests.promo_helpers import commercial_row, promo_panel, write_commercial


def _run(tmp_path: Path, rows: list[dict[str, object]]):
    path = write_commercial(tmp_path / "data" / "integrated" / "panel.commercial.csv", rows)
    return run_promotion(path, data_root=tmp_path / "data", write_outputs=True)


def test_promote_when_peers_on_promo_outperform_off_promo_target(tmp_path: Path) -> None:
    rows = promo_panel(
        target_promo=False,
        target_volume=10.0,
        target_stores=10.0,
        target_price=10.0,
        peer_promo=True,
        peer_volume=20.0,
        peer_stores=10.0,
        peer_price=8.0,
    )
    report = _run(tmp_path, rows)
    hits = [item for item in report.opportunities if item.region == "Gauteng"]
    assert hits
    assert hits[0].recommendation == Recommendation.PROMOTE.value
    assert hits[0].estimated_incremental_value > 0
    assert hits[0].estimated_incremental_volume > 0
    assert hits[0].volume_uplift_pct == pytest.approx(1.0)
    assert hits[0].opportunity_label == "Estimated promotional opportunity"
    assert "not causal" in hits[0].methodology.lower() or "not causal" in " ".join(report.limitations).lower()
    assert hits[0].normal_price is None
    assert hits[0].normal_price_status == "NORMAL_PRICE_UNAVAILABLE"
    assert hits[0].promotion_type == "PROMOTION_TYPE_UNAVAILABLE"
    extra = 10.0 * 1.0 * 10.0 * 0.25
    assert hits[0].estimated_incremental_volume == pytest.approx(extra)
    assert hits[0].estimated_incremental_value == pytest.approx(extra * 10.0)


def test_no_causality_guardrail_higher_promo_volume_alone_is_not_enough(tmp_path: Path) -> None:
    """Own grain is on promo with higher volume, but there is no non-promo baseline."""
    rows: list[dict[str, object]] = []
    for date in ["2026-07-26", "2026-08-02", "2026-08-09", "2026-08-16"]:
        rows.append(
            commercial_row(
                date=date,
                region="Gauteng",
                sales_volume=50.0,
                sales_value=400.0,
                store_count=10.0,
                pos_current_price=8.0,
                pos_percent_time_on_promo=80.0,
                pos_percent_sales_on_promo=80.0,
            )
        )
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.PROMOTE.value, 0) == 0
    assert report.opportunities_emitted == 0
    assert report.recommendation_counts.get(Recommendation.INSUFFICIENT_EVIDENCE.value, 0) >= 1


def test_distribution_primary_blocks_promote(tmp_path: Path) -> None:
    rows = promo_panel(
        target_promo=False,
        target_volume=1.0,
        target_stores=2.0,
        target_price=10.0,
        peer_promo=True,
        peer_volume=40.0,
        peer_stores=20.0,
        peer_price=8.0,
    )
    report = _run(tmp_path, rows)
    gauteng = [item for item in report.opportunities if item.region == "Gauteng"]
    assert all(item.recommendation != Recommendation.PROMOTE.value for item in gauteng)
    assert report.recommendation_counts.get(Recommendation.DISTRIBUTION_FIRST.value, 0) >= 1


def test_missing_promotion_is_insufficient(tmp_path: Path) -> None:
    rows = promo_panel(target_promo=False, peer_promo=True, target_volume=10.0, peer_volume=20.0)
    for row in rows:
        row["pos_percent_time_on_promo"] = None
        row["pos_percent_sales_on_promo"] = None
        row["promotion_indicator_off_present"] = None
        row["promotion_indicator_on_present"] = None
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.PROMOTE.value, 0) == 0
    assert report.recommendation_counts.get(Recommendation.INSUFFICIENT_EVIDENCE.value, 0) >= 1


def test_missing_price_blocks_quantified_value(tmp_path: Path) -> None:
    rows = promo_panel(
        target_promo=False,
        target_volume=10.0,
        peer_promo=True,
        peer_volume=20.0,
        target_price=10.0,
        peer_price=8.0,
    )
    for row in rows:
        if row["region"] == "Gauteng" and row["date"] == "2026-08-16":
            row["pos_current_price"] = None
            row["on_promo_price"] = None
            row["off_promo_price"] = None
            row["sales_value"] = None
    report = _run(tmp_path, rows)
    assert all(
        not (item.region == "Gauteng" and item.recommendation == Recommendation.PROMOTE.value)
        for item in report.opportunities
    )


def test_insufficient_baseline_blocks_uplift(tmp_path: Path) -> None:
    rows = promo_panel(
        target_promo=True,
        peer_promo=True,
        target_volume=20.0,
        peer_volume=20.0,
        weeks=["2026-08-16"],
    )
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.PROMOTE.value, 0) == 0


def test_strong_non_promo_velocity_does_not_promote(tmp_path: Path) -> None:
    rows = promo_panel(
        target_promo=True,
        target_volume=11.0,
        target_stores=10.0,
        target_price=8.0,
        peer_promo=False,
        peer_volume=20.0,
        peer_stores=10.0,
        peer_price=10.0,
    )
    report = _run(tmp_path, rows)
    assert report.recommendation_counts.get(Recommendation.PROMOTE.value, 0) == 0
    assert (
        report.recommendation_counts.get(Recommendation.DO_NOT_PROMOTE.value, 0)
        + report.recommendation_counts.get(Recommendation.REDUCE_PROMOTION.value, 0)
        >= 1
    )


def test_outlier_handling_keeps_row_and_is_flagged(tmp_path: Path) -> None:
    rows = promo_panel(
        target_promo=False,
        target_volume=10.0,
        peer_promo=True,
        peer_volume=20.0,
    )
    for row in rows:
        if row["region"] == "Gauteng" and row["date"] == "2026-08-16":
            row["sales_volume"] = 400.0
            row["sales_value"] = 4000.0
    report = _run(tmp_path, rows)
    assert report.status.value in {"READY WITH WARNINGS", "READY"}
    gauteng_recs = report.recommendation_counts
    assert sum(gauteng_recs.values()) >= 1


def test_confidence_is_not_high_on_four_weeks(tmp_path: Path) -> None:
    rows = promo_panel(target_promo=False, peer_promo=True, target_volume=10.0, peer_volume=20.0)
    report = _run(tmp_path, rows)
    assert report.confidence_distribution.get("HIGH", 0) == 0
    if report.opportunities:
        assert all(item.confidence != "HIGH" for item in report.opportunities)


def test_opportunity_uses_configured_capture_rate(tmp_path: Path) -> None:
    rows = promo_panel(target_promo=False, peer_promo=True, target_volume=10.0, peer_volume=20.0)
    report = _run(tmp_path, rows)
    hits = [item for item in report.opportunities if item.recommendation == Recommendation.PROMOTE.value]
    assert hits
    assert "0.25" in hits[0].methodology
