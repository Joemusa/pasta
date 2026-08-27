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


def detect_outliers(
    frame: pd.DataFrame,
    config: QAConfig,
    source_rows: pd.Series | None = None,
) -> tuple[OutlierSummary, QAIssue | None]:
    method = (config.outlier.method or "mad").lower()
    flagged_index: set[int] = set()
    columns: list[OutlierColumnSummary] = []
    row_ids = source_rows if source_rows is not None else pd.Series(frame.index, index=frame.index)

    for column in OUTLIER_COLUMNS:
        if column not in frame.columns:
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        valid = numeric.dropna()
        if len(valid) < config.outlier.min_observations:
            continue
        if method == "iqr":
            mask = _iqr_mask(valid, config.outlier.iqr_multiplier)
            used = "iqr"
        else:
            mask = _mad_mask(valid, config.outlier.mad_threshold)
            used = "mad"
            if not mask.any():
                # Fall back to IQR when MAD is degenerate or overly quiet on tiny samples.
                iqr_mask = _iqr_mask(valid, config.outlier.iqr_multiplier)
                if iqr_mask.any() and mad_is_degenerate(valid):
                    mask = iqr_mask
                    used = "iqr"

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


def mad_is_degenerate(values: pd.Series) -> bool:
    median = float(values.median())
    mad = float((values - median).abs().median())
    return mad == 0
