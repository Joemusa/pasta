"""Promotion Indicator pivot: state columns, not duplicate grains."""

from __future__ import annotations

import pandas as pd

from backend.agents.integration.models import load_integration_config
from backend.agents.integration.pivot import pivot_promotion_indicator
from backend.tests.integration_helpers import promo_row


def _loaded_promo(rows: list[dict[str, object]]) -> pd.DataFrame:
    raw = pd.DataFrame(rows)
    return pd.DataFrame(
        {
            "product": raw["Product"].astype("string").str.strip(),
            "manufacturer": raw["Manufacturer"].astype("string").str.strip(),
            "brand": raw["Brand"].astype("string").str.strip(),
            "retailer": raw["Retailer"].astype("string").str.strip(),
            "region": raw["Region"].astype("string").str.strip(),
            "date": pd.to_datetime(raw["DDMMMYY"], format="%d %b %y").dt.normalize(),
            "promotion_indicator": pd.to_numeric(raw["Promotion Indicator"]),
            "productsid": raw["ProductsID"].astype("Int64").astype("string"),
            "ave_price_quantity": pd.to_numeric(raw["4 Weeks CY Ave Price Quantity"]),
            "rsp_on_promo": pd.to_numeric(raw["4 Weeks CY Ave RSP On Promo"]),
            "sales_on_promo": pd.to_numeric(raw["4 Weeks CY Sales On Promo"]),
            "time_on_promo": pd.to_numeric(raw["CY % Time On Promo"]),
            "sales_pct_on_promo": pd.to_numeric(raw["4 Weeks CY % Sales On Promo"]),
        }
    )


def test_indicator_zero_and_one_become_off_and_on_columns() -> None:
    wide = pivot_promotion_indicator(
        _loaded_promo(
            [
                promo_row(
                    indicator=0,
                    ave_price=10.0,
                    rsp=11.0,
                    time_on_promo=None,
                    sales_on_promo=None,
                    sales_pct=None,
                ),
                promo_row(indicator=1, ave_price=8.0, rsp=8.0, time_on_promo=40.0, sales_on_promo=50.0, sales_pct=20.0),
            ]
        ),
        load_integration_config(),
    )
    assert len(wide) == 1
    row = wide.iloc[0]
    assert float(row["off_promo_price"]) == 10.0
    assert float(row["on_promo_price"]) == 8.0
    assert float(row["off_promo_rsp"]) == 11.0
    assert float(row["on_promo_rsp"]) == 8.0
    assert pd.isna(row["off_promo_time"])
    assert float(row["on_promo_time"]) == 40.0
    assert float(row["on_promo_sales"]) == 50.0
    assert float(row["on_promo_sales_pct"]) == 20.0
    assert bool(row["promotion_indicator_off_present"]) is True
    assert bool(row["promotion_indicator_on_present"]) is True
    assert row["promotion_states"] == "0|1"
    assert bool(row["flag_multiple_source_matches"]) is False


def test_two_productsids_same_name_remain_one_grain_and_flag_ambiguous() -> None:
    wide = pivot_promotion_indicator(
        _loaded_promo(
            [
                promo_row(indicator=0, productsid=11, ave_price=10.0),
                promo_row(indicator=1, productsid=11, ave_price=8.0),
                promo_row(indicator=0, productsid=22, ave_price=10.0),
                promo_row(indicator=1, productsid=22, ave_price=8.0),
            ]
        ),
        load_integration_config(),
    )
    assert len(wide) == 1
    row = wide.iloc[0]
    assert bool(row["flag_ambiguous_product_mapping"]) is True
    assert bool(row["flag_multiple_source_matches"]) is True
    assert int(row["productsid_count"]) == 2
    assert float(row["off_promo_price"]) == 10.0
    assert float(row["on_promo_price"]) == 8.0


def test_conflicting_prices_for_same_indicator_are_left_missing() -> None:
    wide = pivot_promotion_indicator(
        _loaded_promo(
            [
                promo_row(indicator=0, productsid=11, ave_price=10.0),
                promo_row(indicator=0, productsid=22, ave_price=99.0),
                promo_row(indicator=1, productsid=11, ave_price=8.0),
                promo_row(indicator=1, productsid=22, ave_price=8.0),
            ]
        ),
        load_integration_config(),
    )
    row = wide.iloc[0]
    assert pd.isna(row["off_promo_price"])
    assert float(row["on_promo_price"]) == 8.0
    assert bool(row["flag_ambiguous_product_mapping"]) is True
