from __future__ import annotations

import math

import pandas as pd

from backend.agents.data_qa.models import load_canonical_schema, load_qa_config
from backend.agents.data_qa.standardizer import parse_dates, parse_number, standardise_frame


def test_parse_number_strips_currency_and_commas() -> None:
    assert parse_number("R 1,234.50") == 1234.5
    assert math.isnan(parse_number("n/a"))
    assert math.isnan(parse_number(pd.NA))
    assert math.isnan(parse_number("not-a-number"))


def test_empty_strings_become_null_and_percents_scale_to_0_100() -> None:
    schema = load_canonical_schema()
    config = load_qa_config()
    frame = pd.DataFrame(
        {
            "date": ["Jan 25", "2025-02-01"],
            "manufacturer": [" NESTLE ", ""],
            "brand": ["maggi", "maggi"],
            "product": ["Maggi Noodles", "Maggi Noodles"],
            "sku": ["A1", "A1"],
            "retailer": ["Pick n Pay", "Pick n Pay"],
            "region": ["Gauteng", "Gauteng"],
            "sales_value": ["100", "200"],
            "sales_volume": ["10", "20"],
            "percent_time_on_promo": [0.25, 0.4],
            "promotion_flag": ["yes", "no"],
        }
    )
    out, transformations, _invalid = standardise_frame(frame, schema, config)
    assert pd.isna(out.loc[1, "manufacturer"])
    assert out.loc[0, "manufacturer"] == "Nestle"
    assert out.loc[0, "percent_time_on_promo"] == 25.0
    assert out.loc[1, "percent_time_on_promo"] == 40.0
    assert bool(out.loc[0, "promotion_flag"]) is True
    assert bool(out.loc[1, "promotion_flag"]) is False
    assert any(item.code == "percent_scaled_0_1_to_0_100" for item in transformations)
    assert pd.api.types.is_datetime64_any_dtype(out["date"])


def test_parse_dates_handles_mixed_formats() -> None:
    config = load_qa_config()
    series = pd.Series(["2025-01-15", "Jan 25", "2025/03/01", "15/04/2025", "not-a-date", ""])
    parsed, parsed_count, invalid_count = parse_dates(series, config.date_formats)
    assert parsed_count == 4
    assert invalid_count == 1
    assert parsed.iloc[0] == pd.Timestamp("2025-01-15")
    assert parsed.iloc[1] == pd.Timestamp("2025-01-01")
    assert parsed.iloc[2] == pd.Timestamp("2025-03-01")
    assert parsed.iloc[3] == pd.Timestamp("2025-04-15")
    assert pd.isna(parsed.iloc[4])
    assert pd.isna(parsed.iloc[5])


def test_percent_scale_uses_bulk_unit_interval_despite_rare_outliers() -> None:
    schema = load_canonical_schema()
    config = load_qa_config()
    n = 101
    frame = pd.DataFrame(
        {
            "date": ["2025-01-01"] * n,
            "manufacturer": ["Nestle"] * n,
            "brand": ["Maggi"] * n,
            "product": ["Maggi Noodles"] * n,
            "sku": ["A1"] * n,
            "retailer": ["Pick n Pay"] * n,
            "region": ["Gauteng"] * n,
            "sales_value": [100.0] * n,
            "sales_volume": [10.0] * n,
            "percent_time_on_promo": [0.25] * n,
            "percent_sales_on_promo": [0.1] * 97 + [0.99, 1.0, 1.06, -0.02],
        }
    )
    out, transformations, _invalid = standardise_frame(frame, schema, config)
    assert any(
        item.code == "percent_scaled_0_1_to_0_100" and item.column == "percent_sales_on_promo"
        for item in transformations
    )
    assert float(out.loc[0, "percent_sales_on_promo"]) == 10.0
    assert float(out.loc[n - 3, "percent_sales_on_promo"]) == 100.0
    assert float(out.loc[n - 2, "percent_sales_on_promo"]) == 106.0
    assert float(out.loc[n - 1, "percent_sales_on_promo"]) == -2.0
