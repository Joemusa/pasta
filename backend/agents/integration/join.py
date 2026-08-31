"""Outer-join cleaned POS to the pivoted price/promotion grain.

Unmatched records are kept. Missing metrics stay missing. No historical
observations are manufactured for weeks that exist on only one side.
"""

from __future__ import annotations

import pandas as pd

from backend.agents.integration.models import JOIN_KEY

PROMO_METRICS = (
    "off_promo_price",
    "on_promo_price",
    "off_promo_rsp",
    "on_promo_rsp",
    "off_promo_sales",
    "on_promo_sales",
    "off_promo_time",
    "on_promo_time",
    "off_promo_sales_pct",
    "on_promo_sales_pct",
)


def outer_join(pos: pd.DataFrame, promo_wide: pd.DataFrame) -> pd.DataFrame:
    pos_view = pos.rename(columns={"manufacturer": "manufacturer_pos", "brand": "brand_pos"})
    promo_view = promo_wide.rename(columns={"manufacturer": "manufacturer_promo", "brand": "brand_promo"})
    merged = pos_view.merge(promo_view, on=list(JOIN_KEY), how="outer", indicator=True)
    merged["in_pos"] = merged["_merge"].isin(["left_only", "both"]).astype("boolean")
    merged["in_price_promo"] = merged["_merge"].isin(["right_only", "both"]).astype("boolean")
    merged["manufacturer"] = merged["manufacturer_pos"].combine_first(merged["manufacturer_promo"]).astype("string")
    merged["brand"] = merged["brand_promo"].combine_first(merged["brand_pos"]).astype("string")
    return merged.drop(columns=["manufacturer_pos", "manufacturer_promo", "brand_pos", "brand_promo", "_merge"])
