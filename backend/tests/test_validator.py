from __future__ import annotations

import pandas as pd

from backend.agents.data_qa.models import Severity, load_canonical_schema, load_qa_config
from backend.agents.data_qa.validator import detect_duplicates, validate
from backend.tests.helpers import canonical_rows


def test_safe_duplicates_are_dropped() -> None:
    frame = canonical_rows(n_months=1)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    summary, safe_drop, unsafe_mask = detect_duplicates(frame, load_qa_config())
    assert not bool(unsafe_mask.any())
    assert int(safe_drop.sum()) == 1
    assert summary.safely_dropped == 1


def test_conflicting_duplicates_are_unsafe() -> None:
    frame = canonical_rows(n_months=1)
    conflict = frame.iloc[[0]].copy()
    conflict.loc[conflict.index, "sales_value"] = 1.0
    frame = pd.concat([frame, conflict], ignore_index=True)
    _summary, _safe_drop, unsafe_mask = detect_duplicates(frame, load_qa_config())
    assert bool(unsafe_mask.any())
    assert int(unsafe_mask.sum()) == 2


def test_same_product_different_manufacturer_is_not_a_duplicate() -> None:
    frame = canonical_rows(n_months=1).iloc[[0]].copy()
    other = frame.copy()
    other["manufacturer"] = "Other Co"
    other["sales_value"] = 1.0
    frame = pd.concat([frame, other], ignore_index=True)
    summary, safe_drop, unsafe_mask = detect_duplicates(frame, load_qa_config())
    assert not bool(unsafe_mask.any())
    assert int(safe_drop.sum()) == 0
    assert summary.duplicate_row_count == 0


def test_missing_retailer_is_critical() -> None:
    schema = load_canonical_schema()
    config = load_qa_config()
    frame = canonical_rows(n_months=2).drop(columns=["retailer"])
    issues, _dup, _drop, _reasons = validate(
        frame,
        schema,
        config,
        mapping_missing=["retailer"],
        invalid_parses={},
        constants_applied=[],
    )
    assert any(issue.code == "MISSING_RETAILER" and issue.severity == Severity.CRITICAL for issue in issues)


def test_constants_applied_avoids_missing_retailer_critical() -> None:
    schema = load_canonical_schema()
    config = load_qa_config()
    frame = canonical_rows(n_months=2).drop(columns=["retailer"])
    issues, _dup, _drop, _reasons = validate(
        frame,
        schema,
        config,
        mapping_missing=["retailer"],
        invalid_parses={},
        constants_applied=["retailer"],
    )
    assert not any(issue.code == "MISSING_RETAILER" for issue in issues)
