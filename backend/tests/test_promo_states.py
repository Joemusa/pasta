"""Promo/non-promo separation: missing is not zero; stacked indicator is not a grain flag."""

from __future__ import annotations

from backend.agents.promotion.models import PromoIntensity, PromoState, PromotionConfig, PromotionType
from backend.agents.promotion.states import (
    classify_intensity,
    classify_promotion_state,
    in_baseline_group,
    in_promo_group,
    promotion_type_from_row,
)


def test_zero_pos_percent_is_non_promotion() -> None:
    status, source = classify_promotion_state(
        {"pos_percent_time_on_promo": 0.0, "pos_percent_sales_on_promo": 0.0},
        PromotionConfig(),
    )
    assert status == PromoState.NON_PROMOTION
    assert source == "pos"
    assert in_baseline_group(status, PromoIntensity.NONE) is True


def test_positive_pos_percent_is_promotion() -> None:
    status, source = classify_promotion_state(
        {"pos_percent_time_on_promo": 20.0, "pos_percent_sales_on_promo": None},
        PromotionConfig(),
    )
    assert status == PromoState.PROMOTION
    assert source == "pos"
    assert in_promo_group(status, PromoIntensity.HIGH) is True


def test_missing_promotion_metrics_are_unknown_not_zero() -> None:
    status, source = classify_promotion_state(
        {
            "pos_percent_time_on_promo": None,
            "pos_percent_sales_on_promo": None,
            "promotion_indicator_off_present": None,
            "promotion_indicator_on_present": None,
        },
        PromotionConfig(),
    )
    assert status == PromoState.UNKNOWN
    assert source == "missing"
    intensity, _value = classify_intensity(
        {
            "pos_percent_time_on_promo": None,
            "pos_percent_sales_on_promo": None,
        },
        PromotionConfig(),
    )
    assert intensity == PromoIntensity.UNKNOWN


def test_exclusive_indicator_on_is_promotion() -> None:
    status, source = classify_promotion_state(
        {
            "promotion_indicator_off_present": False,
            "promotion_indicator_on_present": True,
            "pos_percent_time_on_promo": None,
        },
        PromotionConfig(),
    )
    assert status == PromoState.PROMOTION
    assert source == "indicator"


def test_exclusive_indicator_off_is_non_promotion() -> None:
    status, source = classify_promotion_state(
        {
            "promotion_indicator_off_present": True,
            "promotion_indicator_on_present": False,
        },
        PromotionConfig(),
    )
    assert status == PromoState.NON_PROMOTION
    assert source == "indicator"


def test_stacked_indicator_both_present_is_mixed() -> None:
    status, source = classify_promotion_state(
        {
            "promotion_indicator_off_present": True,
            "promotion_indicator_on_present": True,
            "pos_percent_time_on_promo": 40.0,
        },
        PromotionConfig(),
    )
    assert status == PromoState.MIXED
    assert source == "indicator"


def test_intensity_bands() -> None:
    config = PromotionConfig()
    high, high_v = classify_intensity({"pos_percent_time_on_promo": 80.0}, config)
    low, low_v = classify_intensity({"pos_percent_time_on_promo": 10.0}, config)
    mid, _mid_v = classify_intensity({"pos_percent_time_on_promo": 40.0}, config)
    none, _none_v = classify_intensity({"pos_percent_time_on_promo": 0.0}, config)
    assert high == PromoIntensity.HIGH
    assert high_v == 80.0
    assert low == PromoIntensity.LOW
    assert low_v == 10.0
    assert mid == PromoIntensity.MID
    assert none == PromoIntensity.NONE


def test_promotion_type_unavailable() -> None:
    assert promotion_type_from_row({}) == PromotionType.UNAVAILABLE
