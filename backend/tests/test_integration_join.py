"""Join key, outer join, unmatched weeks, and 26 July retention."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.agents.integration import run_integration
from backend.agents.integration.models import JOIN_KEY
from backend.tests.integration_helpers import pos_row, promo_row, write_pos, write_promo


def _run(tmp_path: Path, pos_rows: list[dict[str, object]], promo_rows: list[dict[str, object]]):
    clean_dir = tmp_path / "data" / "clean"
    pos_path = write_pos(clean_dir / "panel.clean.csv", pos_rows)
    promo_path = write_promo(tmp_path / "Unilever_Price_Promo_4weeks.csv", promo_rows)
    return run_integration(
        pos_path,
        promo_path,
        data_root=tmp_path / "data",
        write_outputs=True,
    )


def test_canonical_grain_is_product_retailer_region_date(tmp_path: Path) -> None:
    canonical, report = _run(
        tmp_path,
        [
            pos_row(date="2026-08-16", source_row=1),
            pos_row(date="2026-08-09", source_row=2),
        ],
        [
            promo_row(indicator=0, ddmmmyy="16 Aug 26", ave_price=10.0),
            promo_row(indicator=1, ddmmmyy="16 Aug 26", ave_price=8.0),
            promo_row(indicator=0, ddmmmyy="9 Aug 26", ave_price=10.5),
            promo_row(indicator=1, ddmmmyy="9 Aug 26", ave_price=8.5),
        ],
    )
    assert report.grain == list(JOIN_KEY)
    assert report.join_key == list(JOIN_KEY)
    assert canonical.duplicated(list(JOIN_KEY)).sum() == 0
    assert len(canonical) == 2
    assert report.canonical_duplicate_rows == 0


def test_productsids_are_not_the_join_key(tmp_path: Path) -> None:
    canonical, report = _run(
        tmp_path,
        [pos_row(date="2026-08-16", source_row=1)],
        [
            promo_row(indicator=0, productsid=11, ave_price=10.0),
            promo_row(indicator=1, productsid=11, ave_price=8.0),
            promo_row(indicator=0, productsid=22, ave_price=10.0),
            promo_row(indicator=1, productsid=22, ave_price=8.0),
        ],
    )
    assert len(canonical) == 1
    assert int(canonical.iloc[0]["productsid_count"]) == 2
    assert "11" in str(canonical.iloc[0]["productsid"])
    assert "22" in str(canonical.iloc[0]["productsid"])
    assert bool(canonical.iloc[0]["flag_ambiguous_product_mapping"]) is True
    assert report.canonical_row_count == 1


def test_unmatched_records_are_not_forced_to_match(tmp_path: Path) -> None:
    canonical, report = _run(
        tmp_path,
        [
            pos_row(date="2026-08-16", product="POS Only SKU", source_row=1),
            pos_row(date="2026-08-16", product="Shared SKU", source_row=2),
        ],
        [
            promo_row(indicator=0, product="Shared SKU", ddmmmyy="16 Aug 26", ave_price=9.0),
            promo_row(indicator=1, product="Shared SKU", ddmmmyy="16 Aug 26", ave_price=7.0),
            promo_row(indicator=0, product="Promo Only SKU", ddmmmyy="16 Aug 26", ave_price=6.0, productsid=9),
            promo_row(indicator=1, product="Promo Only SKU", ddmmmyy="16 Aug 26", ave_price=5.0, productsid=9),
        ],
    )
    assert len(canonical) == 3
    pos_only = canonical.loc[canonical["product"].eq("POS Only SKU")].iloc[0]
    promo_only = canonical.loc[canonical["product"].eq("Promo Only SKU")].iloc[0]
    shared = canonical.loc[canonical["product"].eq("Shared SKU")].iloc[0]
    assert bool(pos_only["flag_unmatched_pos"]) is True
    assert bool(pos_only["price_promo_available"]) is False
    assert bool(promo_only["flag_unmatched_price_promo"]) is True
    assert pd.isna(promo_only["sales_value"])
    assert bool(shared["in_pos"]) is True
    assert bool(shared["in_price_promo"]) is True
    assert report.unmatched_pos_records == 1
    assert report.unmatched_price_promo_grains == 1


def test_july_26_pos_week_is_retained_without_promo(tmp_path: Path) -> None:
    canonical, report = _run(
        tmp_path,
        [
            pos_row(date="2026-07-26", current_price=12.5, source_row=1),
            pos_row(date="2026-08-16", current_price=12.5, source_row=2),
        ],
        [
            promo_row(indicator=0, ddmmmyy="16 Aug 26", ave_price=10.0),
            promo_row(indicator=1, ddmmmyy="16 Aug 26", ave_price=8.0),
        ],
    )
    july = canonical.loc[pd.to_datetime(canonical["date"]).dt.strftime("%Y-%m-%d").eq("2026-07-26")]
    assert len(july) == 1
    row = july.iloc[0]
    assert bool(row["in_pos"]) is True
    assert bool(row["flag_price_promo_unavailable_for_period"]) is True
    assert bool(row["price_promo_available"]) is False
    assert bool(row["flag_unmatched_pos"]) is True
    assert pd.isna(row["off_promo_price"])
    assert pd.isna(row["on_promo_price"])
    assert float(row["pos_current_price"]) == 12.5
    assert report.july_26_pos_rows_retained == 1
    assert "2026-07-26" in report.non_overlapping_weeks
    assert "2026-08-16" in report.overlapping_weeks
