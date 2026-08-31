"""Flag numeric outliers without deleting them."""

from __future__ import annotations

import logging

import pandas as pd

from backend.agents.data_qa.models import OutlierColumnSummary, OutlierSummary, QAConfig, QAIssue, Severity

logger = logging.getLogger("backend.agents.data_qa.outlier_detector")

OUTLIER_COLUMNS = (
    "sales_value",
    "sales_volume",
    "store_count",
    "current_price",
    "normal_price",
    "percent_time_on_promo",
    "percent_sales_on_promo",
)


def _mad_mask(values: pd.Series, threshold: float) -> pd.Series:
    median = float(values.median())
    abs_dev = (values - median).abs()
    mad = float(abs_dev.median())
    if mad == 0:
        std = float(values.std(ddof=0))
        if std == 0:
            return pd.Series(False, index=values.index)
        return ((values - median) / std).abs() > threshold
    modified_z = 0.6745 * (values - median) / mad
    return modified_z.abs() > threshold


def _iqr_mask(values: pd.Series, multiplier: float) -> pd.Series:
    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))
    iqr = q3 - q1
    if iqr == 0:
        std = float(values.std(ddof=0))
        if std == 0:
            return pd.Series(False, index=values.index)
        return ((values - float(values.median())) / std).abs() > 3.5
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return (values < lower) | (values > upper)


def mad_is_degenerate(values: pd.Series) -> bool:
    median = float(values.median())
    mad = float((values - median).abs().median())
    return mad == 0


def _series_outlier_mask(values: pd.Series, config: QAConfig, method: str) -> tuple[pd.Series, str]:
    if method == "iqr":
        return _iqr_mask(values, config.outlier.iqr_multiplier), "iqr"
    mask = _mad_mask(values, config.outlier.mad_threshold)
    used = "mad"
    if not mask.any() and mad_is_degenerate(values):
        iqr_mask = _iqr_mask(values, config.outlier.iqr_multiplier)
        if iqr_mask.any():
            return iqr_mask, "iqr"
    return mask, used


def _column_outlier_mask(frame: pd.DataFrame, column: str, config: QAConfig) -> tuple[pd.Series, str]:
    numeric = pd.to_numeric(frame[column], errors="coerce")
    method = (config.outlier.method or "mad").lower()
    group_fields = [field for field in config.outlier.group_fields if field in frame.columns]
    empty = pd.Series(False, index=frame.index)

    if group_fields:
        mask = empty.copy()
        used = f"{method}_grouped"
        grouped = frame.groupby(group_fields, dropna=False, sort=False)
        for _, group in grouped:
            values = numeric.loc[group.index].dropna()
            if len(values) < config.outlier.min_observations:
                continue
            group_mask, group_method = _series_outlier_mask(values, config, method)
            if group_mask.any():
                mask.loc[group_mask[group_mask].index] = True
                used = f"{group_method}_grouped"
        return mask, used

    valid = numeric.dropna()
    if len(valid) < config.outlier.min_observations:
        return empty, method
    return _series_outlier_mask(valid, config, method)


def detect_outliers(
    frame: pd.DataFrame,
    config: QAConfig,
    source_rows: pd.Series | None = None,
) -> tuple[OutlierSummary, QAIssue | None]:
    flagged_index: set[int] = set()
    columns: list[OutlierColumnSummary] = []
    row_ids = source_rows if source_rows is not None else pd.Series(frame.index, index=frame.index)

    for column in OUTLIER_COLUMNS:
        if column not in frame.columns:
            continue
        mask, used = _column_outlier_mask(frame, column, config)
        count = int(mask.sum())
        if count == 0:
            continue
        sample_rows = row_ids.loc[mask[mask].index].astype(int).head(10).tolist()
        flagged_index.update(mask[mask].index.tolist())
        columns.append(
            OutlierColumnSummary(
                column=column,
                method=used,
                count=count,
                sample_source_rows=sample_rows,
            )
        )

    summary = OutlierSummary(total_flagged_rows=len(flagged_index), columns=columns)
    issue = None
    if columns:
        affected = ", ".join(f"{item.column} ({item.count})" for item in columns)
        issue = QAIssue(
            code="OUTLIERS_FLAGGED",
            severity=Severity.WARNING,
            message=(
                f"Flagged {summary.total_flagged_rows} rows as potential outliers "
                f"without deleting them: {affected}"
            ),
            row_count=summary.total_flagged_rows,
        )
    logger.info(
        "outliers_ok flagged_rows=%s columns=%s",
        summary.total_flagged_rows,
        [item.column for item in columns],
    )
    return summary, issue
