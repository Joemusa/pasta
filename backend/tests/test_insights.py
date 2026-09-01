from __future__ import annotations

import pandas as pd

from backend.agents.reporting.insights import build_snapshot
from backend.tests.helpers import canonical_rows


def test_snapshot_ranks_manufacturers_by_value() -> None:
    frame = canonical_rows(n_months=2)
    snapshot = build_snapshot(frame)
    assert snapshot.has_data is True
    assert snapshot.n_dates == 2
    assert snapshot.n_retailers == 3
    assert snapshot.top_manufacturers
    assert snapshot.top_manufacturers[0].share > 0
    assert abs(sum(item.share for item in snapshot.top_manufacturers) - 1.0) < 0.15


def test_empty_frame_has_no_snapshot() -> None:
    snapshot = build_snapshot(pd.DataFrame())
    assert snapshot.has_data is False
    assert snapshot.total_value == 0
