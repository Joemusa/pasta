"""Promotion classification: missing is not zero; indicator is not a grain flag."""

from __future__ import annotations

from backend.agents.price.models import PriceConfig, PromotionStatus
from backend.agents.price.promotion import classify_promotion, promotion_is_controlled


def test_zero_pos_percent_is_non_promotion() -> None:
    status, source = classify_promotion(
        {"pos_percent_time_on_promo": 0.0, "pos_percent_sales_on_promo": 0.0},
        PriceConfig(),
    )
    assert status == PromotionStatus.NON_PROMOTION
    assert source == "pos"
    assert promotion_is_controlled(status) is True


def test_positive_pos_percent_is_promotion() -> None:
    status, source = classify_promotion(
        {"pos_percent_time_on_promo": 20.0, "pos_percent_sales_on_promo": None},
        PriceConfig(),
    )
    assert status == PromotionStatus.PROMOTION
    assert source == "pos"


def test_missing_promotion_metrics_are_unknown_not_zero() -> None:
    status, source = classify_promotion(
        {
            "pos_percent_time_on_promo": None,
            "pos_percent_sales_on_promo": None,
            "off_promo_time": None,
            "on_promo_time": None,
            "off_promo_sales_pct": None,
            "on_promo_sales_pct": None,
        },
        PriceConfig(),
    )
    assert status == PromotionStatus.UNKNOWN
    assert source == "missing"
    assert promotion_is_controlled(status) is False


def test_extract_metrics_used_when_pos_missing() -> None:
    status, source = classify_promotion(
        {
            "pos_percent_time_on_promo": None,
            "pos_percent_sales_on_promo": None,
            "on_promo_time": 15.0,
        },
        PriceConfig(),
    )
    assert status == PromotionStatus.PROMOTION
    assert source == "rolling_4w_cy"
