"""Builders for Commercial Data Integration Layer tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

POS_COLUMNS = [
    "date",
    "manufacturer",
    "product",
    "retailer",
    "region",
    "sales_value",
    "sales_volume",
    "store_count",
    "current_price",
    "percent_time_on_promo",
    "percent_sales_on_promo",
    "_source_row",
]

PROMO_COLUMNS = [
    "Promotion Indicator",
    "Brand",
    "Manufacturer",
    "Product",
    "ProductsID",
    "Region",
    "Retailer",
    "DDMMMYY",
    "CY % Time On Promo",
    "4 Weeks CY Ave Price Quantity",
    "4 Weeks CY Sales On Promo",
    "4 Weeks CY Ave RSP On Promo",
    "4 Weeks CY % Sales On Promo",
]


def pos_row(
    *,
    date: str = "2026-08-16",
    manufacturer: str = "Unilever",
    product: str = "Handy Andy All Purpose Cleaner Lemon 750ml",
    retailer: str = "Checkers",
    region: str = "Gauteng",
    sales_value: float | None = 100.0,
    sales_volume: float | None = 10.0,
    store_count: float | None = 5.0,
    current_price: float | None = 12.5,
    percent_time_on_promo: float | None = None,
    percent_sales_on_promo: float | None = None,
    source_row: int = 1,
) -> dict[str, object]:
    return {
        "date": date,
        "manufacturer": manufacturer,
        "product": product,
        "retailer": retailer,
        "region": region,
        "sales_value": sales_value,
        "sales_volume": sales_volume,
        "store_count": store_count,
        "current_price": current_price,
        "percent_time_on_promo": percent_time_on_promo,
        "percent_sales_on_promo": percent_sales_on_promo,
        "_source_row": source_row,
    }


def promo_row(
    *,
    indicator: int = 0,
    brand: str = "Handy Andy",
    manufacturer: str = "Unilever",
    product: str = "Handy Andy All Purpose Cleaner Lemon 750ml",
    productsid: int = 1001,
    region: str = "Gauteng",
    retailer: str = "Checkers",
    ddmmmyy: str = "16 Aug 26",
    time_on_promo: float | None = None,
    ave_price: float | None = 12.0,
    sales_on_promo: float | None = None,
    rsp: float | None = None,
    sales_pct: float | None = None,
) -> dict[str, object]:
    return {
        "Promotion Indicator": indicator,
        "Brand": brand,
        "Manufacturer": manufacturer,
        "Product": product,
        "ProductsID": productsid,
        "Region": region,
        "Retailer": retailer,
        "DDMMMYY": ddmmmyy,
        "CY % Time On Promo": time_on_promo,
        "4 Weeks CY Ave Price Quantity": ave_price,
        "4 Weeks CY Sales On Promo": sales_on_promo,
        "4 Weeks CY Ave RSP On Promo": rsp,
        "4 Weeks CY % Sales On Promo": sales_pct,
    }


def write_pos(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=POS_COLUMNS).to_csv(path, index=False)
    return path


def write_promo(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=PROMO_COLUMNS).to_csv(path, index=False)
    return path
