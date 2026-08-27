from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.agents.data_qa import run_data_qa
from backend.agents.data_qa.models import Status
from backend.tests.helpers import canonical_rows


def _write_csv(path: Path, frame: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def test_agent_pass_with_warnings_on_messy_but_usable_file(tmp_path: Path) -> None:
    frame = canonical_rows(n_months=12)
    frame = frame.rename(
        columns={
            "date": "Month",
            "product": "Product Name",
            "sales_value": "Sales Value",
            "sales_volume": "Units",
            "store_count": "Stores",
            "current_price": "Price",
            "normal_price": "Regular Price",
            "percent_time_on_promo": "% Time on Promo",
            "percent_sales_on_promo": "% Sales on Promo",
            "promotion_flag": "On Promo",
        }
    )
    frame.loc[0, "region"] = ""
    frame.loc[1, "manufacturer"] = ""
    frame.loc[2, "Sales Value"] = 0
    frame.loc[3, "Price"] = 9_999.0
    duplicate = frame.iloc[[4]].copy()
    frame = pd.concat([frame, duplicate], ignore_index=True)

    source = _write_csv(tmp_path / "inbox" / "sample.csv", frame)
    original_bytes = source.read_bytes()
    data_root = tmp_path / "data"
    report = run_data_qa(source, data_root=data_root)

    assert source.read_bytes() == original_bytes
    assert report.status in {Status.PASS, Status.PASS_WITH_WARNINGS, Status.PARTIAL_PASS}
    assert report.analysis_ready is True
    assert report.capabilities.commercial_brain is True
    assert report.capabilities.distribution is True
    assert report.column_mapping["Sales Value"] == "sales_value"
    assert (data_root / "raw" / "sample.csv").exists()
    assert report.clean_output_path is not None
    clean = pd.read_csv(report.clean_output_path)
    assert "sales_value" in clean.columns
    assert report.outliers.total_flagged_rows >= 0
    assert any(issue.code == "ZERO_SALES" for issue in report.warnings)
    dumped = report.to_json_dict()
    assert set(dumped["capabilities"]) == {
        "distribution",
        "price",
        "promotion",
        "macro_overlay",
        "social_evidence",
        "commercial_brain",
    }


def test_agent_fails_when_retailer_missing(tmp_path: Path) -> None:
    frame = canonical_rows(n_months=12).drop(columns=["retailer"])
    source = _write_csv(tmp_path / "no_retailer.csv", frame)
    report = run_data_qa(source, data_root=tmp_path / "data")
    assert report.status == Status.FAIL
    assert report.analysis_ready is False
    assert report.capabilities.commercial_brain is False
    assert any(issue.code == "MISSING_RETAILER" for issue in report.critical_issues)
    assert report.clean_output_path is None


def test_agent_fails_on_unreadable_file(tmp_path: Path) -> None:
    source = tmp_path / "broken.csv"
    source.write_text("not,a\nvalid\x00file", encoding="utf-8")
    # Completely empty / non-table files still need to fail closed.
    empty = tmp_path / "empty.xlsx"
    empty.write_bytes(b"this is not an excel file")
    report = run_data_qa(empty, data_root=tmp_path / "data")
    assert report.status == Status.FAIL
    assert report.analysis_ready is False
    assert report.critical_issues[0].code == "FILE_UNREADABLE"


def test_cli_help_is_available() -> None:
    from backend.agents.data_qa.__main__ import build_parser

    parser = build_parser()
    help_text = parser.format_help()
    assert "Deterministic Data QA Agent" in help_text


def test_committed_sample_is_analysis_ready(tmp_path: Path) -> None:
    source = Path("backend/data/raw/sample_pos.csv")
    report = run_data_qa(source, data_root=tmp_path / "data")
    assert report.status in {Status.PASS, Status.PASS_WITH_WARNINGS, Status.PARTIAL_PASS}
    assert report.analysis_ready is True
    assert report.capabilities.commercial_brain is True
    assert report.clean_output_path is not None


def test_titled_excel_with_blank_prices_fails_closed_on_missing_retailer(tmp_path: Path) -> None:
    path = tmp_path / "panel.xlsx"
    rows = [
        ["Monthly Trended Export"],
        ["Measure by MonthYear2"],
        [""],
        [
            "MonthYear2",
            "Manufacturer",
            "Product",
            "Trended Sales Value",
            "Trended Sales Volume",
            "Trended Ave Price (Value/Volume)",
        ],
        ["Jul 24", "Tiger Brands", "Spaghetti 500g", "1000", "80", ""],
        ["Aug 24", "Tiger Brands", "Spaghetti 500g", "1100", "90", "12.2"],
    ]
    pd.DataFrame(rows).to_excel(path, index=False, header=False, engine="openpyxl")
    report = run_data_qa(path, data_root=tmp_path / "data")
    assert report.status == Status.FAIL
    assert any(issue.code == "MISSING_RETAILER" for issue in report.critical_issues)
    assert report.column_mapping["MonthYear2"] == "date"
    assert report.column_mapping["Trended Sales Value"] == "sales_value"
