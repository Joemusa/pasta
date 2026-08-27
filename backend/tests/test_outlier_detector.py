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
