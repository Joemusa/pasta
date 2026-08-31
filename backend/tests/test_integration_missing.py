"""Missing values stay missing. Prices and promo metrics are never fabricated."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.agents.integration import run_integration
from backend.tests.integration_helpers import pos_row, promo_row, write_pos, write_promo


def _run(tmp_path: Path, pos_rows: list[dict[str, object]], promo_rows: list[dict[str, object]]):
    clean_dir = tmp_path / "data" / "clean"
    pos_path = write_pos(clean_dir / "panel.clean.csv", pos_rows)
    promo_path = write_promo(tmp_path / "promo.csv", promo_rows)
    return run_integration(pos_path, promo_path, data_root=tmp_path / "data", write_outputs=True)


def test_missing_price_is_not_converted_to_zero(tmp_path: Path) -> None:
    canonical, _report = _run(
        tmp_path,
        [pos_row(date="2026-08-16", current_price=None, source_row=1)],
        [
            promo_row(indicator=0, ave_price=None, rsp=None),
            promo_row(indicator=1, ave_price=None, rsp=None),
        ],
    )
    row = canonical.iloc[0]
    assert pd.isna(row["pos_current_price"])
    assert pd.isna(row["off_promo_price"])
    assert pd.isna(row["on_promo_price"])
    assert bool(row["flag_missing_price"]) is True
    written = pd.read_csv(tmp_path / "data" / "integrated" / "panel.commercial.csv")
    assert pd.isna(written.iloc[0]["off_promo_price"])
    assert pd.isna(written.iloc[0]["on_promo_price"])
    assert pd.isna(written.iloc[0]["pos_current_price"])


def test_missing_promotion_metrics_are_not_converted_to_zero(tmp_path: Path) -> None:
    canonical, _report = _run(
        tmp_path,
        [pos_row(date="2026-08-16", percent_time_on_promo=None, percent_sales_on_promo=None, source_row=1)],
        [
            promo_row(indicator=0, ave_price=10.0, time_on_promo=None, sales_on_promo=None, sales_pct=None),
            promo_row(indicator=1, ave_price=8.0, time_on_promo=None, sales_on_promo=None, sales_pct=None),
        ],
    )
    row = canonical.iloc[0]
    for column in (
        "off_promo_time",
        "on_promo_time",
        "off_promo_sales",
        "on_promo_sales",
        "off_promo_sales_pct",
        "on_promo_sales_pct",
        "pos_percent_time_on_promo",
        "pos_percent_sales_on_promo",
    ):
        assert pd.isna(row[column])
    assert bool(row["flag_missing_promotion_metrics"]) is True


def test_on_promo_price_is_not_copied_from_off_promo_or_pos(tmp_path: Path) -> None:
    canonical, _report = _run(
        tmp_path,
        [pos_row(date="2026-08-16", current_price=12.5, source_row=1)],
        [
            promo_row(indicator=0, ave_price=10.0, rsp=11.0),
            promo_row(indicator=1, ave_price=None, rsp=None),
        ],
    )
    row = canonical.iloc[0]
    assert float(row["off_promo_price"]) == 10.0
    assert float(row["pos_current_price"]) == 12.5
    assert pd.isna(row["on_promo_price"])
    assert pd.isna(row["on_promo_rsp"])


def test_july_26_does_not_inherit_later_week_prices(tmp_path: Path) -> None:
    canonical, _report = _run(
        tmp_path,
        [
            pos_row(date="2026-07-26", current_price=None, source_row=1),
            pos_row(date="2026-08-16", current_price=12.5, source_row=2),
        ],
        [
            promo_row(indicator=0, ddmmmyy="16 Aug 26", ave_price=10.0, rsp=11.0, time_on_promo=30.0),
            promo_row(indicator=1, ddmmmyy="16 Aug 26", ave_price=8.0, rsp=8.0, time_on_promo=30.0),
        ],
    )
    july = canonical.loc[pd.to_datetime(canonical["date"]).dt.strftime("%Y-%m-%d").eq("2026-07-26")].iloc[0]
    august = canonical.loc[pd.to_datetime(canonical["date"]).dt.strftime("%Y-%m-%d").eq("2026-08-16")].iloc[0]
    assert float(august["off_promo_price"]) == 10.0
    assert pd.isna(july["off_promo_price"])
    assert pd.isna(july["on_promo_price"])
    assert pd.isna(july["off_promo_time"])
    assert pd.isna(july["pos_current_price"])
    assert bool(july["flag_price_promo_unavailable_for_period"]) is True


def test_pos_promo_percent_is_not_copied_into_extract_columns(tmp_path: Path) -> None:
    canonical, _report = _run(
        tmp_path,
        [pos_row(date="2026-08-16", percent_time_on_promo=55.0, percent_sales_on_promo=40.0, source_row=1)],
        [
            promo_row(indicator=0, ave_price=10.0, time_on_promo=None, sales_pct=None),
            promo_row(indicator=1, ave_price=8.0, time_on_promo=None, sales_pct=None),
        ],
    )
    row = canonical.iloc[0]
    assert float(row["pos_percent_time_on_promo"]) == 55.0
    assert float(row["pos_percent_sales_on_promo"]) == 40.0
    assert pd.isna(row["off_promo_time"])
    assert pd.isna(row["on_promo_time"])
    assert pd.isna(row["off_promo_sales_pct"])
    assert pd.isna(row["on_promo_sales_pct"])


def test_rsp_is_not_labelled_or_filled_as_normal_price(tmp_path: Path) -> None:
    canonical, report = _run(
        tmp_path,
        [pos_row(date="2026-08-16", source_row=1)],
        [
            promo_row(indicator=0, ave_price=10.0, rsp=None),
            promo_row(indicator=1, ave_price=8.0, rsp=7.5),
        ],
    )
    row = canonical.iloc[0]
    assert "normal_price" not in canonical.columns
    assert pd.isna(row["off_promo_rsp"])
    assert float(row["on_promo_rsp"]) == 7.5
    assert "not proven as normal shelf price" in report.field_sources["off_promo_rsp"]
    assert "not proven as normal shelf price" in report.field_sources["on_promo_rsp"]
