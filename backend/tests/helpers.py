"""Shared builders for Data QA tests."""

from __future__ import annotations

from datetime import date

import pandas as pd


def canonical_rows(n_months: int = 12, extra: dict[str, list[object]] | None = None) -> pd.DataFrame:
    months = [date(2025, month, 1) for month in range(1, n_months + 1)]
    rows: list[dict[str, object]] = []
    products = [
        ("Tiger Brands", "Fatti's & Moni's", "Fatti's & Moni's Spaghetti 500g", "6001110001"),
        ("Nestle", "Maggi", "Maggi 2-Minute Noodles Chicken 73g", "6001110002"),
        ("Indofood", "Indomie", "Indomie Mi Goreng 80g", "6001110003"),
        ("Barilla Group", "Barilla", "Barilla Penne 500g", "6001110004"),
    ]
    retailers = ["Pick n Pay", "Shoprite", "Spar"]
    for month in months:
        for retailer in retailers:
            for manufacturer, brand, product, sku in products:
                rows.append(
                    {
                        "date": month.isoformat(),
                        "manufacturer": manufacturer,
                        "brand": brand,
                        "product": product,
                        "sku": sku,
                        "retailer": retailer,
                        "region": "Gauteng",
                        "sales_value": 120000.0,
                        "sales_volume": 8000.0,
                        "store_count": 240,
                        "current_price": 15.0,
                        "normal_price": 17.5,
                        "percent_time_on_promo": 0.2,
                        "percent_sales_on_promo": 0.35,
                        "promotion_flag": 1,
                    }
                )
    frame = pd.DataFrame(rows)
    if extra:
        for column, values in extra.items():
            frame[column] = values
    return frame
