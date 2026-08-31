"""Builders for Promotion Agent V1 tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

WEEKS = ["2026-07-26", "2026-08-02", "2026-08-09", "2026-08-16"]
REGIONS = ["Gauteng", "Western Cape", "KwaZulu-Natal", "Eastern Cape"]


def commercial_row(
    *,
    date: str = "2026-08-16",
    manufacturer: str = "Unilever",
    brand: str = "Handy Andy",
    product: str = "Handy Andy Lemon 750ml",
    retailer: str = "Checkers",
    region: str = "Gauteng",
    sales_value: float | None = 100.0,
    sales_volume: float | None = 10.0,
    store_count: float | None = 10.0,
    pos_current_price: float | None = 10.0,
    pos_percent_time_on_promo: float | None = 0.0,
    pos_percent_sales_on_promo: float | None = 0.0,
    off_present: bool | None = None,
    on_present: bool | None = None,
    off_promo_price: float | None = None,
    on_promo_price: float | None = None,
    in_pos: bool = True,
    flag_ambiguous_product_mapping: bool = False,
) -> dict[str, object]:
    if off_present is None and on_present is None:
        if pos_percent_time_on_promo is None and pos_percent_sales_on_promo is None:
            off_flag: object = pd.NA
            on_flag: object = pd.NA
        elif (pos_percent_time_on_promo or 0) > 0 or (pos_percent_sales_on_promo or 0) > 0:
            off_flag = False
            on_flag = True
        else:
            off_flag = True
            on_flag = False
    else:
        off_flag = pd.NA if off_present is None else off_present
        on_flag = pd.NA if on_present is None else on_present
    return {
        "product": product,
        "manufacturer": manufacturer,
        "brand": brand,
        "retailer": retailer,
        "region": region,
        "date": date,
        "sales_value": sales_value,
        "sales_volume": sales_volume,
        "store_count": store_count,
        "pos_current_price": pos_current_price,
        "pos_percent_time_on_promo": pos_percent_time_on_promo,
        "pos_percent_sales_on_promo": pos_percent_sales_on_promo,
        "off_promo_time": pd.NA,
        "on_promo_time": pd.NA,
        "off_promo_sales_pct": pd.NA,
        "on_promo_sales_pct": pd.NA,
        "off_promo_rsp": pd.NA,
        "on_promo_rsp": pd.NA,
        "off_promo_price": off_promo_price if off_promo_price is not None else pd.NA,
        "on_promo_price": on_promo_price if on_promo_price is not None else pd.NA,
        "promotion_indicator_off_present": off_flag,
        "promotion_indicator_on_present": on_flag,
        "in_pos": "true" if in_pos else "false",
        "flag_ambiguous_product_mapping": "true" if flag_ambiguous_product_mapping else "false",
        "flag_missing_promotion_metrics": "true"
        if pos_percent_time_on_promo is None and pos_percent_sales_on_promo is None
        else "false",
    }


def promo_panel(
    *,
    product: str = "Handy Andy Lemon 750ml",
    retailer: str = "Checkers",
    target_region: str = "Gauteng",
    target_promo: bool = False,
    target_volume: float = 10.0,
    target_stores: float = 10.0,
    target_price: float = 10.0,
    peer_promo: bool = True,
    peer_volume: float = 20.0,
    peer_stores: float = 10.0,
    peer_price: float = 8.0,
    weeks: list[str] | None = None,
) -> list[dict[str, object]]:
    """Same SKU x retailer across regions. Target vs peer promo/volume for like-for-like tests."""
    rows: list[dict[str, object]] = []
    for date in weeks or WEEKS:
        for region in REGIONS:
            target = region == target_region
            promo = target_promo if target else peer_promo
            volume = target_volume if target else peer_volume
            stores = target_stores if target else peer_stores
            price = target_price if target else peer_price
            rows.append(
                commercial_row(
                    date=date,
                    product=product,
                    retailer=retailer,
                    region=region,
                    pos_current_price=price,
                    sales_volume=volume,
                    sales_value=price * volume,
                    store_count=stores,
                    pos_percent_time_on_promo=40.0 if promo else 0.0,
                    pos_percent_sales_on_promo=40.0 if promo else 0.0,
                    on_promo_price=price if promo else None,
                    off_promo_price=None if promo else price,
                )
            )
    return rows


def write_commercial(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path
