from __future__ import annotations

import math

import pandas as pd

from backend.agents.data_qa.models import load_canonical_schema, load_qa_config
from backend.agents.data_qa.standardizer import parse_number, standardise_frame


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
