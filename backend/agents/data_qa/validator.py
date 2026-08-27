"""Deterministic validation of required fields, duplicates, dates, and values."""

from __future__ import annotations

import logging

import pandas as pd

from backend.agents.data_qa.models import (
    CanonicalSchema,
    DuplicateSummary,
    FieldDtype,
    QAConfig,
    QAIssue,
    Severity,
)

logger = logging.getLogger("backend.agents.data_qa.validator")

METRIC_NON_NEGATIVE = ("sales_value", "sales_volume", "store_count")
PRICE_FIELDS = ("current_price", "normal_price")
PERCENT_FIELDS = ("percent_time_on_promo", "percent_sales_on_promo")


def _issue(
    code: str,
    severity: Severity,
    message: str,
    column: str | None = None,
    row_count: int = 0,
    sample_values: list[str] | None = None,
) -> QAIssue:
    return QAIssue(
        code=code,
        severity=severity,
        message=message,
        column=column,
        row_count=row_count,
        sample_values=sample_values or [],
    )


def _samples(series: pd.Series, limit: int = 5) -> list[str]:
    values = series.dropna().astype(str).head(limit).tolist()
    return values


def duplicate_key_columns(frame: pd.DataFrame, config: QAConfig) -> list[str]:
    available: list[str] = []
    prefer_sku = "sku" in frame.columns and frame["sku"].notna().any()
    for field in config.duplicate_key_fields:
        if field == "product" and prefer_sku:
            continue
        if field == "sku" and not prefer_sku:
            continue
        if field in frame.columns:
            available.append(field)
    return available


def detect_duplicates(
    frame: pd.DataFrame,
    config: QAConfig,
) -> tuple[DuplicateSummary, pd.Series, pd.Series]:
    """Return summary, safe-duplicate drop mask, and unsafe-group mask."""
    keys = duplicate_key_columns(frame, config)
    empty_mask = pd.Series(False, index=frame.index)
    if len(keys) < 2:
        return DuplicateSummary(key_fields=keys), empty_mask, empty_mask.copy()

    key_frame = frame[keys]
    duplicated = key_frame.duplicated(keep=False)
    if not duplicated.any():
        return DuplicateSummary(key_fields=keys), empty_mask, empty_mask.copy()

    metric_cols = [
        col
        for col in (*METRIC_NON_NEGATIVE, *PRICE_FIELDS, *PERCENT_FIELDS, "promotion_flag")
        if col in frame.columns
    ]
    unsafe_groups = 0
    safe_drop = pd.Series(False, index=frame.index)
    unsafe_mask = pd.Series(False, index=frame.index)
    grouped = frame.loc[duplicated].groupby(keys, dropna=False, sort=False)
    for _, group in grouped:
        if len(group) < 2:
            continue
        if metric_cols:
            comparable = group[metric_cols]
            conflict = False
            for col in metric_cols:
                nonempty = comparable[col].dropna()
                if nonempty.empty:
                    continue
                if nonempty.nunique(dropna=True) > 1:
                    conflict = True
                    break
            if conflict:
                unsafe_groups += 1
                unsafe_mask.loc[group.index] = True
                continue
        safe_drop.loc[group.index[1:]] = True

    summary = DuplicateSummary(
        key_fields=keys,
        duplicate_row_count=int(duplicated.sum()),
        unsafe_group_count=unsafe_groups,
        safely_dropped=int(safe_drop.sum()),
    )
    return summary, safe_drop, unsafe_mask


def invalid_row_mask(frame: pd.DataFrame) -> pd.Series:
    """Rows that must not enter the clean dataset."""
    mask = pd.Series(False, index=frame.index)
    if "date" in frame.columns:
        mask = mask | frame["date"].isna()
    product_ok = pd.Series(False, index=frame.index)
    if "product" in frame.columns:
        product_ok = product_ok | frame["product"].notna()
    if "sku" in frame.columns:
        product_ok = product_ok | frame["sku"].notna()
    if "product" in frame.columns or "sku" in frame.columns:
        mask = mask | ~product_ok
    if "retailer" in frame.columns:
        mask = mask | frame["retailer"].isna()
    for col in ("sales_value", "sales_volume"):
        if col in frame.columns:
            mask = mask | frame[col].isna() | (frame[col] < 0)
    if "store_count" in frame.columns:
        mask = mask | (frame["store_count"] < 0)
    for col in PRICE_FIELDS:
        if col in frame.columns:
            present = frame[col].notna()
            mask = mask | (present & (frame[col] <= 0))
    for col in PERCENT_FIELDS:
        if col in frame.columns:
            present = frame[col].notna()
            mask = mask | (present & ((frame[col] < 0) | (frame[col] > 100)))
    return mask


def row_exclusion_reasons(
    frame: pd.DataFrame,
    *,
    safe_drop: pd.Series,
    unsafe_mask: pd.Series,
) -> pd.Series:
    """Return a reason code per row; empty string means the row is kept."""
    buckets: dict[object, list[str]] = {idx: [] for idx in frame.index}

    def add(mask: pd.Series, code: str) -> None:
        if mask is None or not bool(mask.any()):
            return
        for idx in frame.index[mask.fillna(False)]:
            buckets[idx].append(code)

    if "date" in frame.columns:
        add(frame["date"].isna(), "INVALID_DATE")
    product_ok = pd.Series(False, index=frame.index)
    if "product" in frame.columns:
        product_ok = product_ok | frame["product"].notna()
    if "sku" in frame.columns:
        product_ok = product_ok | frame["sku"].notna()
    if "product" in frame.columns or "sku" in frame.columns:
        add(~product_ok, "MISSING_PRODUCT_OR_SKU")
    if "retailer" in frame.columns:
        add(frame["retailer"].isna(), "MISSING_RETAILER")
    for col in ("sales_value", "sales_volume"):
        if col in frame.columns:
            add(frame[col].isna() | (frame[col] < 0), f"INVALID_{col.upper()}")
    if "store_count" in frame.columns:
        add(frame["store_count"] < 0, "INVALID_STORE_COUNT")
    for col in PRICE_FIELDS:
        if col in frame.columns:
            add(frame[col].notna() & (frame[col] <= 0), "INVALID_PRICE")
    for col in PERCENT_FIELDS:
        if col in frame.columns:
            add(frame[col].notna() & ((frame[col] < 0) | (frame[col] > 100)), "INVALID_PERCENT")
    add(safe_drop.reindex(frame.index).fillna(False).astype(bool), "SAFE_DUPLICATE")
    add(unsafe_mask.reindex(frame.index).fillna(False).astype(bool), "UNSAFE_DUPLICATE")
    return pd.Series({idx: ";".join(codes) for idx, codes in buckets.items()}, index=frame.index)


def validate(
    frame: pd.DataFrame,
    schema: CanonicalSchema,
    config: QAConfig,
    *,
    mapping_missing: list[str],
    invalid_parses: dict[str, int],
    constants_applied: list[str],
) -> tuple[list[QAIssue], DuplicateSummary, pd.Series, pd.Series]:
    issues: list[QAIssue] = []
    n_rows = len(frame)
    applied = set(constants_applied)
    unmapped = [name for name in mapping_missing if name not in applied]
    present = set(frame.columns)

    def available(column: str) -> bool:
        return column in present or column in applied

    has_product = available("product")
    has_sku = available("sku")
    if not has_product and not has_sku:
        issues.append(
            _issue(
                "MISSING_PRODUCT_OR_SKU",
                Severity.CRITICAL,
                "Neither product nor sku could be mapped from the source file"
                if "product" in unmapped and "sku" in unmapped
                else "Neither product nor sku is available after mapping",
            )
        )
    if not available("retailer"):
        issues.append(
            _issue(
                "MISSING_RETAILER",
                Severity.CRITICAL,
                (
                    "Retailer column could not be mapped from the source file"
                    if "retailer" in unmapped
                    else "Retailer column is missing and is required for basic commercial analysis"
                ),
                column="retailer",
            )
        )
    if not available("date"):
        issues.append(
            _issue(
                "NO_VALID_DATES",
                Severity.CRITICAL,
                "Date column is missing; no valid dates are available",
                column="date",
            )
        )
    if not available("sales_value"):
        issues.append(
            _issue(
                "MISSING_SALES_VALUE",
                Severity.CRITICAL,
                "Sales value column is missing and is required for basic commercial analysis",
                column="sales_value",
            )
        )
    if not available("sales_volume"):
        issues.append(
            _issue(
                "MISSING_SALES_VOLUME",
                Severity.CRITICAL,
                "Sales volume column is missing and is required for basic commercial analysis",
                column="sales_volume",
            )
        )

    if "date" in present:
        invalid_dates = int(invalid_parses.get("date", 0))
        remaining_null = int(frame["date"].isna().sum())
        parsed = n_rows - remaining_null
        if parsed == 0:
            issues.append(
                _issue(
                    "NO_VALID_DATES",
                    Severity.CRITICAL,
                    "No values in the date column could be parsed as dates",
                    column="date",
                    row_count=n_rows,
                    sample_values=_samples(frame["date"].astype(str)),
                )
            )
        elif n_rows and (invalid_dates / n_rows) > config.invalid_date_rate_threshold:
            issues.append(
                _issue(
                    "INVALID_DATE_RATE",
                    Severity.CRITICAL,
                    (
                        f"Invalid date parsing rate {invalid_dates / n_rows:.1%} "
                        f"exceeds threshold {config.invalid_date_rate_threshold:.0%}"
                    ),
                    column="date",
                    row_count=invalid_dates,
                )
            )
        elif invalid_dates:
            issues.append(
                _issue(
                    "INVALID_DATES",
                    Severity.WARNING,
                    f"{invalid_dates} date values could not be parsed and will be dropped",
                    column="date",
                    row_count=invalid_dates,
                )
            )

    for col in ("sales_value", "sales_volume"):
        if col not in present:
            continue
        failed = int(invalid_parses.get(col, 0))
        if n_rows and (failed / n_rows) > config.invalid_numeric_rate_threshold:
            issues.append(
                _issue(
                    "INVALID_NUMERIC_RATE",
                    Severity.CRITICAL,
                    (
                        f"{col} has unparseable numeric rate {failed / n_rows:.1%} "
                        f"exceeding threshold {config.invalid_numeric_rate_threshold:.0%}"
                    ),
                    column=col,
                    row_count=failed,
                )
            )
        null_rate = float(frame[col].isna().mean()) if n_rows else 1.0
        if null_rate >= config.required_null_rate_threshold and null_rate > 0:
            issues.append(
                _issue(
                    f"MISSING_{col.upper()}",
                    Severity.CRITICAL,
                    f"{col} is missing in {null_rate:.1%} of rows",
                    column=col,
                    row_count=int(frame[col].isna().sum()),
                )
            )

    if "product" in frame.columns or "sku" in frame.columns:
        identity_null = pd.Series(True, index=frame.index)
        if "product" in frame.columns:
            identity_null = identity_null & frame["product"].isna()
        if "sku" in frame.columns:
            identity_null = identity_null & frame["sku"].isna()
        identity_rate = float(identity_null.mean()) if n_rows else 1.0
        if identity_rate >= config.required_null_rate_threshold and identity_rate > 0:
            issues.append(
                _issue(
                    "MISSING_PRODUCT_OR_SKU",
                    Severity.CRITICAL,
                    f"Product and SKU are both missing in {identity_rate:.1%} of rows",
                    row_count=int(identity_null.sum()),
                )
            )

    if "retailer" in present:
        null_rate = float(frame["retailer"].isna().mean()) if n_rows else 1.0
        if null_rate >= config.required_null_rate_threshold and null_rate > 0:
            issues.append(
                _issue(
                    "MISSING_RETAILER",
                    Severity.CRITICAL,
                    f"Retailer is missing in {null_rate:.1%} of rows",
                    column="retailer",
                    row_count=int(frame["retailer"].isna().sum()),
                )
            )

    for col in METRIC_NON_NEGATIVE:
        if col not in present:
            continue
        bad = frame[col].notna() & (frame[col] < 0)
        if bad.any():
            issues.append(
                _issue(
                    "IMPOSSIBLE_NEGATIVE",
                    Severity.CRITICAL if col in ("sales_value", "sales_volume") else Severity.WARNING,
                    f"{col} contains negative values",
                    column=col,
                    row_count=int(bad.sum()),
                    sample_values=_samples(frame.loc[bad, col]),
                )
            )

    for col in PRICE_FIELDS:
        if col not in present:
            continue
        bad = frame[col].notna() & (frame[col] <= 0)
        if bad.any():
            issues.append(
                _issue(
                    "IMPOSSIBLE_PRICE",
                    Severity.WARNING,
                    f"{col} must be > 0 where present",
                    column=col,
                    row_count=int(bad.sum()),
                    sample_values=_samples(frame.loc[bad, col]),
                )
            )

    for col in PERCENT_FIELDS:
        if col not in present:
            continue
        bad = frame[col].notna() & ((frame[col] < 0) | (frame[col] > 100))
        if bad.any():
            issues.append(
                _issue(
                    "IMPOSSIBLE_PERCENT",
                    Severity.WARNING,
                    f"{col} must be between 0 and 100 after standardisation",
                    column=col,
                    row_count=int(bad.sum()),
                    sample_values=_samples(frame.loc[bad, col]),
                )
            )

    if "region" not in present:
        issues.append(
            _issue("MISSING_REGION", Severity.WARNING, "Region is not present in the source file", column="region")
        )
    elif frame["region"].isna().any():
        issues.append(
            _issue(
                "MISSING_REGION",
                Severity.WARNING,
                "Region has missing values",
                column="region",
                row_count=int(frame["region"].isna().sum()),
            )
        )

    if "manufacturer" not in present:
        issues.append(
            _issue(
                "MISSING_MANUFACTURER",
                Severity.WARNING,
                "Manufacturer is not present in the source file",
                column="manufacturer",
            )
        )
    elif frame["manufacturer"].isna().any():
        issues.append(
            _issue(
                "MISSING_MANUFACTURER",
                Severity.WARNING,
                "Manufacturer has missing values",
                column="manufacturer",
                row_count=int(frame["manufacturer"].isna().sum()),
            )
        )

    promo_present = any(col in present and frame[col].notna().any() for col in (*PERCENT_FIELDS, "promotion_flag"))
    if not promo_present:
        issues.append(
            _issue(
                "MISSING_PROMOTION_FIELDS",
                Severity.WARNING,
                "No promotion fields were mapped (percent_time_on_promo, percent_sales_on_promo, or promotion_flag)",
            )
        )

    price_present = any(col in present and frame[col].notna().any() for col in PRICE_FIELDS)
    if not price_present:
        issues.append(
            _issue(
                "MISSING_PRICE_FIELDS",
                Severity.WARNING,
                "No price fields were mapped (current_price or normal_price)",
            )
        )
    elif "normal_price" not in present or not frame["normal_price"].notna().any():
        issues.append(
            _issue(
                "MISSING_NORMAL_PRICE",
                Severity.WARNING,
                "Normal price is not present; price analysis will rely on current_price only",
                column="normal_price",
            )
        )

    if "store_count" not in present or not frame["store_count"].notna().any():
        issues.append(
            _issue(
                "MISSING_STORE_COUNT",
                Severity.WARNING,
                "Store count is not present; the Distribution agent cannot run",
                column="store_count",
            )
        )

    for col in ("sales_value", "sales_volume"):
        if col not in present:
            continue
        zeros = frame[col].notna() & (frame[col] == 0)
        if zeros.any():
            issues.append(
                _issue(
                    "ZERO_SALES",
                    Severity.WARNING,
                    f"{col} contains zeros",
                    column=col,
                    row_count=int(zeros.sum()),
                )
            )

    if "date" in present:
        distinct = int(frame["date"].dropna().nunique())
        if 0 < distinct < config.min_history_periods:
            issues.append(
                _issue(
                    "SPARSE_HISTORY",
                    Severity.WARNING,
                    (
                        f"Only {distinct} distinct dates found; "
                        f"minimum for robust history is {config.min_history_periods}"
                    ),
                    column="date",
                    row_count=distinct,
                )
            )

    for col, failed in invalid_parses.items():
        if col == "date" or failed == 0:
            continue
        spec = schema.by_name().get(col)
        if (
            spec
            and spec.dtype in {FieldDtype.NUMBER, FieldDtype.PERCENT, FieldDtype.FLAG}
            and n_rows
            and (failed / n_rows) <= config.invalid_numeric_rate_threshold
        ):
            issues.append(
                _issue(
                    "INVALID_NUMERIC",
                    Severity.WARNING,
                    f"{failed} values in {col} could not be parsed as numeric",
                    column=col,
                    row_count=failed,
                )
            )

    dup_summary, safe_drop, unsafe_mask = detect_duplicates(frame, config)
    unsafe = bool(unsafe_mask.any())
    if unsafe:
        issues.append(
            _issue(
                "UNSAFE_DUPLICATES",
                Severity.CRITICAL,
                (
                    "Duplicate records share the same grain but have conflicting metrics "
                    "and cannot be safely deduplicated"
                ),
                row_count=int(unsafe_mask.sum()),
            )
        )
    elif dup_summary.safely_dropped:
        issues.append(
            _issue(
                "DUPLICATES_DROPPED",
                Severity.WARNING,
                f"Dropped {dup_summary.safely_dropped} exact duplicate rows at grain {dup_summary.key_fields}",
                row_count=dup_summary.safely_dropped,
            )
        )

    drop_invalid = invalid_row_mask(frame)
    drop_mask = drop_invalid | safe_drop | unsafe_mask
    reasons = row_exclusion_reasons(frame, safe_drop=safe_drop, unsafe_mask=unsafe_mask)
    logger.info("validate_ok issues=%s drop_rows=%s", len(issues), int(drop_mask.sum()))
    return issues, dup_summary, drop_mask, reasons
