"""Promotion vs non-promotion classification. Missing promo metrics are not treated as zero."""

from __future__ import annotations

from backend.agents.promotion.models import PromoIntensity, PromoState, PromotionConfig, PromotionType

POS_PROMO_FIELDS = ("pos_percent_time_on_promo", "pos_percent_sales_on_promo")
EXTRACT_INTENSITY_FIELDS = ("on_promo_time", "on_promo_sales_pct")


def _positive_promo(value: object, threshold: float) -> bool | None:
    """True if strictly promotional, False if present and not promotional, None if missing."""
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > threshold:
        return True
    return False


def _as_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    if text in {"", "<na>", "nan", "none", "<nat>"}:
        return None
    return None


def _finite_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        if value != value:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_promotion_state(row: dict[str, object], config: PromotionConfig) -> tuple[PromoState, str]:
    """Use the explicit indicator when only one stacked state is present. Missing is not non-promo."""
    off_present = _as_bool(row.get("promotion_indicator_off_present"))
    on_present = _as_bool(row.get("promotion_indicator_on_present"))
    if on_present is True and off_present is False:
        return PromoState.PROMOTION, "indicator"
    if off_present is True and on_present is False:
        return PromoState.NON_PROMOTION, "indicator"
    if on_present is True and off_present is True:
        return PromoState.MIXED, "indicator"

    pos_hits = [_positive_promo(row.get(field), config.promo_percent_threshold) for field in POS_PROMO_FIELDS]
    if any(item is True for item in pos_hits):
        return PromoState.PROMOTION, "pos"
    if any(item is False for item in pos_hits) and not any(item is True for item in pos_hits):
        return PromoState.NON_PROMOTION, "pos"
    return PromoState.UNKNOWN, "missing"


def _scale_intensity(value: object) -> float | None:
    """Return 0-100 intensity. Extract time/sales shares that look like 0-1 are scaled."""
    number = _finite_number(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        return number * 100.0
    return number


def promo_intensity_value(row: dict[str, object]) -> float | None:
    for field in POS_PROMO_FIELDS:
        number = _finite_number(row.get(field))
        if number is not None:
            return number
    for field in EXTRACT_INTENSITY_FIELDS:
        scaled = _scale_intensity(row.get(field))
        if scaled is not None:
            return scaled
    return None


def classify_intensity(row: dict[str, object], config: PromotionConfig) -> tuple[PromoIntensity, float | None]:
    state, _source = classify_promotion_state(row, config)
    intensity = promo_intensity_value(row)
    if state == PromoState.NON_PROMOTION:
        return PromoIntensity.NONE, 0.0 if intensity is None else intensity
    if intensity is None:
        if state == PromoState.PROMOTION:
            return PromoIntensity.HIGH, None
        return PromoIntensity.UNKNOWN, None
    if intensity <= config.promo_percent_threshold:
        return PromoIntensity.NONE, intensity
    if intensity < config.low_promo_intensity_max:
        return PromoIntensity.LOW, intensity
    if intensity >= config.high_promo_intensity_min:
        return PromoIntensity.HIGH, intensity
    return PromoIntensity.MID, intensity


def promotion_type_from_row(_row: dict[str, object]) -> PromotionType:
    """No promotion-type field exists in the canonical extract."""
    return PromotionType.UNAVAILABLE


def in_promo_group(state: PromoState, intensity: PromoIntensity) -> bool:
    if state == PromoState.PROMOTION:
        return True
    return intensity == PromoIntensity.HIGH


def in_baseline_group(state: PromoState, intensity: PromoIntensity) -> bool:
    if state == PromoState.NON_PROMOTION or intensity == PromoIntensity.NONE:
        return True
    return intensity == PromoIntensity.LOW
