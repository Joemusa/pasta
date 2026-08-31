"""Promotion vs non-promotion classification. Missing promo metrics are not treated as zero."""

from __future__ import annotations

from backend.agents.price.models import PriceConfig, PromotionStatus

POS_PROMO_FIELDS = ("pos_percent_time_on_promo", "pos_percent_sales_on_promo")
EXTRACT_PROMO_FIELDS = (
    "off_promo_time",
    "on_promo_time",
    "off_promo_sales_pct",
    "on_promo_sales_pct",
)


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


def classify_promotion(
    row: dict[str, object],
    config: PriceConfig,
    *,
    prefer_pos: bool = True,
) -> tuple[PromotionStatus, str]:
    """Return (status, source). Indicator 0/1 is not a grain-level on/off flag."""
    threshold = config.promo_percent_threshold
    pos_hits = [_positive_promo(row.get(field), threshold) for field in POS_PROMO_FIELDS]
    if prefer_pos and any(item is not None for item in pos_hits):
        if any(item is True for item in pos_hits):
            return PromotionStatus.PROMOTION, "pos"
        if all(item is False for item in pos_hits):
            return PromotionStatus.NON_PROMOTION, "pos"
        # Mix of False and missing among POS fields: treat as NON_PROMOTION only if a False exists
        # and nothing is True — a present zero is evidence; missing is not.
        if any(item is False for item in pos_hits) and not any(item is True for item in pos_hits):
            return PromotionStatus.NON_PROMOTION, "pos"

    extract_hits = [_positive_promo(row.get(field), threshold) for field in EXTRACT_PROMO_FIELDS]
    if any(item is True for item in extract_hits):
        return PromotionStatus.PROMOTION, "rolling_4w_cy"
    if any(item is False for item in extract_hits) and not any(item is True for item in extract_hits):
        return PromotionStatus.NON_PROMOTION, "rolling_4w_cy"
    return PromotionStatus.UNKNOWN, "missing"


def promotion_is_controlled(status: PromotionStatus) -> bool:
    return status in {PromotionStatus.PROMOTION, PromotionStatus.NON_PROMOTION}
