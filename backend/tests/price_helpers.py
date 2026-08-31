"""Builders for Price Agent V1 tests."""

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
    in_pos: bool = True,
    flag_ambiguous_product_mapping: bool = False,
) -> dict[str, object]:
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
        "in_pos": "true" if in_pos else "false",
        "flag_ambiguous_product_mapping": "true" if flag_ambiguous_product_mapping else "false",
        "flag_missing_promotion_metrics": "true"
        if pos_percent_time_on_promo is None and pos_percent_sales_on_promo is None
        else "false",
    }


def panel_for_product(
    *,
    product: str = "Handy Andy Lemon 750ml",
    retailer: str = "Checkers",
    target_region: str = "Gauteng",
    target_price: float = 10.0,
    target_volume: float = 10.0,
    target_stores: float = 10.0,
    peer_price: float = 10.0,
    peer_volume: float = 10.0,
    peer_stores: float = 10.0,
    promo: float = 0.0,
    weeks: list[str] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for date in weeks or WEEKS:
        for region in REGIONS:
            target = region == target_region
            rows.append(
                commercial_row(
                    date=date,
                    product=product,
                    retailer=retailer,
                    region=region,
                    pos_current_price=target_price if target else peer_price,
                    sales_volume=target_volume if target else peer_volume,
                    sales_value=(target_price if target else peer_price)
                    * (target_volume if target else peer_volume),
                    store_count=target_stores if target else peer_stores,
                    pos_percent_time_on_promo=promo,
                    pos_percent_sales_on_promo=promo,
                )
            )
    return rows


def write_commercial(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path
