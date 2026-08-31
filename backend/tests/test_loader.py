from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.agents.data_qa.loader import detect_header_row, load_table
from backend.agents.data_qa.models import load_canonical_schema, load_qa_config


def test_detects_header_below_title_rows(tmp_path: Path) -> None:
    path = tmp_path / "titled.xlsx"
    title = pd.DataFrame([["Monthly Trended Export"], ["Measure by MonthYear2, Category"]])
    body = pd.DataFrame(
        [
            ["MonthYear2", "Manufacturer", "Product", "Retailer", "Trended Sales Value", "Trended Sales Volume"],
            ["Jul 24", "Tiger Brands", "Spaghetti 500g", "Shoprite", "1000", "80"],
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        combined = pd.concat([title, pd.DataFrame([[""]]), body], ignore_index=True)
        combined.to_excel(writer, index=False, header=False, sheet_name="Export")

    schema = load_canonical_schema()
    config = load_qa_config()
    preview = pd.read_excel(path, header=None, dtype=object, engine="openpyxl")
    header_row = detect_header_row(preview, schema, config)
    assert header_row >= 2
    frame, detected, sheet = load_table(path, schema, config)
    assert detected == header_row
    assert sheet == "Export"
    assert "MonthYear2" in frame.columns
    assert len(frame) == 1
