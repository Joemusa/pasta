"""End-to-end Commercial Data Integration Layer tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.agents.integration import IntegrationLoadError, IntegrationStatus, run_integration
from backend.agents.integration.__main__ import build_parser
from backend.agents.integration.models import JOIN_KEY
from backend.tests.integration_helpers import pos_row, promo_row, write_pos, write_promo


def test_agent_writes_canonical_csv_and_report(tmp_path: Path) -> None:
    clean_dir = tmp_path / "data" / "clean"
    pos_path = write_pos(
        clean_dir / "panel.clean.csv",
        [
            pos_row(date="2026-07-26", source_row=1),
            pos_row(date="2026-08-16", source_row=2),
            pos_row(date="2026-08-16", manufacturer="Reckitt Benckiser", product="Dettol 1l", source_row=3),
        ],
    )
    promo_path = write_promo(
        tmp_path / "Unilever_Price_Promo_4weeks.csv",
        [
            promo_row(indicator=0, ddmmmyy="16 Aug 26", ave_price=10.0, time_on_promo=None),
            promo_row(indicator=1, ddmmmyy="16 Aug 26", ave_price=8.0, time_on_promo=25.0, sales_on_promo=40.0),
        ],
    )
    canonical, report = run_integration(pos_path, promo_path, data_root=tmp_path / "data")
    assert report.status == IntegrationStatus.READY_WITH_WARNINGS
    assert report.pos_row_count == 3
    assert report.price_promo_row_count == 2
    assert report.canonical_row_count == 3
    assert (tmp_path / "data" / "integrated" / "panel.commercial.csv").exists()
    assert (tmp_path / "data" / "integration_reports" / "panel.integration.json").exists()
    assert canonical.duplicated(list(JOIN_KEY)).sum() == 0
    assert report.july_26_pos_rows_retained == 1
    weekly = {item.date: item for item in report.weekly}
    assert weekly["2026-07-26"].pos_records == 1
    assert weekly["2026-07-26"].price_promo_records == 0
    assert weekly["2026-07-26"].matched == 0
    assert weekly["2026-07-26"].match_pct == 0.0
    assert weekly["2026-08-16"].matched == 1


def test_refuses_raw_pos_inputs(tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    pos_path = write_pos(raw_dir / "upload.csv", [pos_row()])
    promo_path = write_promo(tmp_path / "promo.csv", [promo_row(indicator=0), promo_row(indicator=1)])
    with pytest.raises(IntegrationLoadError, match="cleaned"):
        run_integration(pos_path, promo_path, data_root=tmp_path / "data")


def test_duplicate_pos_grain_fails_closed(tmp_path: Path) -> None:
    clean_dir = tmp_path / "data" / "clean"
    pos_path = write_pos(
        clean_dir / "panel.clean.csv",
        [pos_row(source_row=1), pos_row(source_row=2)],
    )
    promo_path = write_promo(tmp_path / "promo.csv", [promo_row(indicator=0), promo_row(indicator=1)])
    with pytest.raises(IntegrationLoadError, match="not unique"):
        run_integration(pos_path, promo_path, data_root=tmp_path / "data")


def test_cli_help_mentions_join_key() -> None:
    help_text = build_parser().format_help()
    assert "Product + Retailer + Region + Date" in help_text
    assert "price-promo" in help_text


def test_real_sources_if_present() -> None:
    pos = Path("backend/data/clean/New Discovery_2026-08-27 (3).clean.csv")
    promo = Path("Unilever_Price_Promo_4weeks.csv")
    if not pos.exists() or not promo.exists():
        pytest.skip("Committed POS clean file or Unilever price/promo extract is not in this checkout")
    canonical, report = run_integration(pos, promo, write_outputs=False)
    assert report.join_key == list(JOIN_KEY)
    assert report.pos_row_count == 66026
    assert report.price_promo_row_count == 147016
    assert report.price_promo_grain_count == 72803
    assert report.canonical_row_count == 66026 + 72803 - 9138
    assert report.matched_pos_records == 9138
    assert report.july_26_pos_rows_retained > 0
    assert "2026-07-26" in report.non_overlapping_weeks
    assert report.overlapping_weeks == ["2026-08-02", "2026-08-09", "2026-08-16"]
    assert canonical.duplicated(list(JOIN_KEY)).sum() == 0
    july = canonical.loc[pd.to_datetime(canonical["date"]).dt.strftime("%Y-%m-%d").eq("2026-07-26")]
    assert july["in_pos"].all()
    assert (~july["in_price_promo"].fillna(False)).all()
    assert july["off_promo_price"].isna().all()
    assert not (july["off_promo_price"] == 0).any()
    assert report.status == IntegrationStatus.READY_WITH_WARNINGS
    assert report.canonical_duplicate_rows == 0
    assert report.product_mapping.ids_with_multiple_product_names == 0
    assert report.product_mapping.products_with_multiple_ids > 0
