"""Quality flags for the canonical commercial grain. Missing stays missing."""

from __future__ import annotations

import pandas as pd

from backend.agents.integration.join import PROMO_METRICS

PRICE_COLUMNS = ("pos_current_price", "off_promo_price", "on_promo_price")
RSP_COLUMNS = ("off_promo_rsp", "on_promo_rsp")
PROMO_METRIC_COLUMNS = (
    "off_promo_sales",
    "on_promo_sales",
    "off_promo_time",
    "on_promo_time",
    "off_promo_sales_pct",
    "on_promo_sales_pct",
)


def _all_missing(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    present = [column for column in columns if column in frame.columns]
    if not present:
        return pd.Series(True, index=frame.index, dtype="boolean")
    missing = frame[present[0]].isna()
    for column in present[1:]:
        missing = missing & frame[column].isna()
    return missing.astype("boolean")


def _any_present(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    present = [column for column in columns if column in frame.columns]
    if not present:
        return pd.Series(False, index=frame.index, dtype="boolean")
    found = frame[present[0]].notna()
    for column in present[1:]:
        found = found | frame[column].notna()
    return found.astype("boolean")


def attach_flags(canonical: pd.DataFrame, promo_dates: set[pd.Timestamp]) -> pd.DataFrame:
    out = canonical.copy()
    if "in_pos" not in out.columns or "in_price_promo" not in out.columns:
        raise ValueError("canonical frame must include in_pos and in_price_promo")

    out["price_promo_available"] = out["in_price_promo"].astype("boolean")
    out["flag_unmatched_pos"] = (out["in_pos"] & ~out["in_price_promo"]).astype("boolean")
    out["flag_unmatched_price_promo"] = (out["in_price_promo"] & ~out["in_pos"]).astype("boolean")
    if "flag_multiple_source_matches" not in out.columns:
        out["flag_multiple_source_matches"] = pd.Series(False, index=out.index, dtype="boolean")
    else:
        out["flag_multiple_source_matches"] = out["flag_multiple_source_matches"].fillna(False).astype("boolean")
    if "flag_ambiguous_product_mapping" not in out.columns:
        out["flag_ambiguous_product_mapping"] = pd.Series(False, index=out.index, dtype="boolean")
    else:
        out["flag_ambiguous_product_mapping"] = out["flag_ambiguous_product_mapping"].fillna(False).astype("boolean")

    out["flag_missing_price"] = _all_missing(out, PRICE_COLUMNS)
    out["flag_missing_rsp"] = _all_missing(out, RSP_COLUMNS)
    out["flag_missing_promotion_metrics"] = _all_missing(out, PROMO_METRIC_COLUMNS)
    out["flag_price_promo_unavailable_for_period"] = (~out["date"].isin(promo_dates)).astype("boolean")

    out["price_enabled"] = _any_present(out, PRICE_COLUMNS)
    promo_enabled_cols = (*PROMO_METRIC_COLUMNS, "pos_percent_time_on_promo", "pos_percent_sales_on_promo")
    out["promotion_enabled"] = _any_present(out, promo_enabled_cols)

    for column in PROMO_METRICS:
        if column not in out.columns:
            out[column] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    return out
