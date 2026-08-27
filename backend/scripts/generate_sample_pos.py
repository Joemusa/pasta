"""Generate the committed sample POS extract used to demonstrate the Data QA Agent."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_pos.csv"

PRODUCTS = [
    ("Tiger Brands", "Fatti's & Moni's", "Fatti's & Moni's Spaghetti 500g", "6001110001"),
    ("Nestle", "Maggi", "Maggi 2-Minute Noodles Chicken 73g", "6001110002"),
    ("Indofood", "Indomie", "Indomie Mi Goreng 80g", "6001110003"),
    ("Barilla Group", "Barilla", "Barilla Penne 500g", "6001110004"),
]
RETAILERS = ["Pick n Pay", "Shoprite", "Spar"]
REGIONS = ["Gauteng", "Western Cape", "KwaZulu-Natal"]

HEADERS = [
    "Month",
    "Retailer",
    "Region",
    "Manufacturer",
    "Brand",
    "Product Name",
    "SKU",
    "Sales Value",
    "Units",
    "Stores",
    "Price",
    "Regular Price",
    "% Time on Promo",
    "% Sales on Promo",
    "On Promo",
]


def build_rows() -> list[list[object]]:
    rows: list[list[object]] = []
    for month in range(1, 13):
        month_label = date(2025, month, 1).isoformat()
        for retailer_idx, retailer in enumerate(RETAILERS):
            region = REGIONS[retailer_idx]
            for sku_idx, (manufacturer, brand, product, sku) in enumerate(PRODUCTS):
                base_value = 80_000 + month * 1_500 + sku_idx * 12_000 + retailer_idx * 4_000
                volume = 5_000 + month * 80 + sku_idx * 400
                price = round(base_value / volume, 2)
                promo = 0.15 + (sku_idx * 0.05)
                rows.append(
                    [
                        month_label,
                        retailer,
                        region,
                        manufacturer,
                        brand,
                        product,
                        sku,
                        base_value,
                        volume,
                        180 + retailer_idx * 40,
                        price,
                        round(price * 1.12, 2),
                        promo,
                        promo + 0.1,
                        1 if promo >= 0.2 else 0,
                    ]
                )

    # Intentional quality issues for the sample report.
    rows[0][2] = ""  # missing region
    rows[1][3] = ""  # missing manufacturer
    rows[2][7] = 0  # zero sales value
    rows[5][10] = 999.99  # price outlier
    rows[20][7] = "R 12,500.00"  # currency formatting
    rows[21][0] = "Feb 25"  # alternative date format for that row's month
    rows[22][13] = 0.9
    rows.append(list(rows[10]))  # exact duplicate, safe to drop
    return rows


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerows(build_rows())
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
