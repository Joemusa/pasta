from __future__ import annotations

import pandas as pd

from backend.agents.data_qa.models import load_qa_config
from backend.agents.data_qa.outlier_detector import detect_outliers


def test_outliers_are_flagged_not_removed() -> None:
    values = [10.0] * 20 + [10_000.0]
    frame = pd.DataFrame({"sales_value": values, "_source_row": range(1, 22)})
    summary, issue = detect_outliers(frame, load_qa_config(), source_rows=frame["_source_row"])
    assert summary.total_flagged_rows >= 1
    assert any(col.column == "sales_value" for col in summary.columns)
    assert issue is not None
    assert len(frame) == 21


def test_outliers_are_detected_within_product_not_across_skus() -> None:
    n = 12
    frame = pd.DataFrame(
        {
            "product": ["Small SKU"] * n + ["Large SKU"] * n,
            "sales_value": [10.0] * n + [10_000.0] * n,
            "_source_row": range(1, 2 * n + 1),
        }
    )
    summary, issue = detect_outliers(frame, load_qa_config(), source_rows=frame["_source_row"])
    assert summary.total_flagged_rows == 0
    assert issue is None

    frame.loc[0, "sales_value"] = 10_000.0
    summary, issue = detect_outliers(frame, load_qa_config(), source_rows=frame["_source_row"])
    assert summary.total_flagged_rows == 1
    assert issue is not None
