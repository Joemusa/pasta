"""Orchestrate load → map → standardise → validate → outliers → capabilities → report."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pandas as pd

from backend.agents.data_qa.capability_checker import analysis_ready, check_capabilities, distinct_dates
from backend.agents.data_qa.loader import LoadError, load_table
from backend.agents.data_qa.models import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_SCHEMA_PATH,
    CanonicalSchema,
    Capabilities,
    OutlierSummary,
    QAConfig,
    QAIssue,
    QAReport,
    Severity,
    Status,
    load_canonical_schema,
    load_qa_config,
)
from backend.agents.data_qa.outlier_detector import detect_outliers
from backend.agents.data_qa.schema_detector import apply_mapping, detect_columns
from backend.agents.data_qa.standardizer import standardise_frame
from backend.agents.data_qa.validator import validate

logger = logging.getLogger("backend.agents.data_qa")

BLOCKING_CODES = {
    "FILE_UNREADABLE",
    "NO_VALID_DATES",
    "INVALID_DATE_RATE",
    "MISSING_PRODUCT_OR_SKU",
    "MISSING_RETAILER",
    "MISSING_SALES_VALUE",
    "MISSING_SALES_VOLUME",
    "UNSAFE_DUPLICATES",
    "INVALID_NUMERIC_RATE",
}

CANONICAL_OUTPUT_ORDER = [
    "date",
    "manufacturer",
    "brand",
    "product",
    "sku",
    "retailer",
    "region",
    "sales_value",
    "sales_volume",
    "store_count",
    "current_price",
    "normal_price",
    "percent_time_on_promo",
    "percent_sales_on_promo",
    "promotion_flag",
]


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def preserve_raw(source: Path, raw_dir: Path) -> Path:
    """Copy the upload into data/raw without overwriting the source or an existing raw copy."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    source = source.resolve()
    dest = (raw_dir / source.name).resolve()
    if dest == source:
        logger.info("raw_already_in_place path=%s", source)
        return source
    if dest.exists():
        logger.info("raw_exists_skip_copy dest=%s", dest)
        return dest
    shutil.copy2(source, dest)
    logger.info("raw_preserved source=%s dest=%s", source, dest)
    return dest


def _fail_report(
    *,
    input_file: str,
    raw_preserved_at: str,
    message: str,
    code: str = "FILE_UNREADABLE",
) -> QAReport:
    issue = QAIssue(code=code, severity=Severity.CRITICAL, message=message)
    return QAReport(
        status=Status.FAIL,
        analysis_ready=False,
        quality_score=0,
        critical_issues=[issue],
        capabilities=Capabilities(
            distribution=False,
            price=False,
            promotion=False,
            macro_overlay=False,
            social_evidence=False,
            commercial_brain=False,
        ),
        input_file=_display_path(Path(input_file)) if input_file else "",
        raw_preserved_at=_display_path(Path(raw_preserved_at)) if raw_preserved_at else "",
    )


def _quality_score(
    *,
    ready: bool,
    critical_count: int,
    warning_count: int,
    drop_rate: float,
    outlier_rows: int,
    row_count: int,
    sparse: bool,
) -> int:
    score = 100.0
    if not ready:
        score -= 35
    score -= 12 * critical_count
    score -= 4 * warning_count
    score -= min(20.0, drop_rate * 100)
    if row_count:
        score -= min(10.0, 100.0 * outlier_rows / row_count)
    if sparse:
        score -= 6
    return int(max(0, min(100, round(score))))


def _status(
    *,
    ready: bool,
    blocking: bool,
    warnings: list[QAIssue],
    critical: list[QAIssue],
    drop_rate: float,
    partial_threshold: float,
) -> Status:
    if blocking or not ready:
        return Status.FAIL
    if drop_rate >= partial_threshold and drop_rate > 0:
        return Status.PARTIAL_PASS
    if critical or warnings:
        return Status.PASS_WITH_WARNINGS
    return Status.PASS


def _write_clean_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    export = frame.copy()
    if "date" in export.columns:
        export["date"] = pd.to_datetime(export["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    export.to_csv(path, index=False)


def _order_columns(frame: pd.DataFrame) -> pd.DataFrame:
    leading = [col for col in CANONICAL_OUTPUT_ORDER if col in frame.columns]
    trailing = [col for col in frame.columns if col not in leading and col != "_source_row"]
    ordered = leading + trailing
    if "_source_row" in frame.columns:
        ordered.append("_source_row")
    return frame[ordered]


def run_data_qa(
    input_path: str | Path,
    *,
    data_root: str | Path | None = None,
    config_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    write_outputs: bool = True,
) -> QAReport:
    """Run the deterministic Data QA Agent on a CSV or Excel upload."""
    _configure_logging()
    source = Path(input_path).expanduser().resolve()
    if data_root:
        root = Path(data_root).expanduser().resolve()
    elif source.parent.name == "raw":
        root = source.parents[1]
    else:
        root = Path("backend/data").resolve()
    raw_dir = root / "raw"
    clean_dir = root / "clean"
    reports_dir = root / "qa_reports"

    schema: CanonicalSchema = load_canonical_schema(
        Path(schema_path) if schema_path else DEFAULT_SCHEMA_PATH
    )
    config: QAConfig = load_qa_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)

    logger.info("qa_start input=%s data_root=%s", source, root)
    try:
        raw_copy = preserve_raw(source, raw_dir)
    except OSError as exc:
        report = _fail_report(
            input_file=str(source),
            raw_preserved_at="",
            message=f"Could not preserve raw upload: {exc}",
        )
        return _persist_report(report, reports_dir, source.stem, write_outputs)

    try:
        frame, header_row, sheet_name = load_table(source, schema, config)
    except LoadError as exc:
        report = _fail_report(
            input_file=str(source),
            raw_preserved_at=str(raw_copy),
            message=str(exc),
        )
        return _persist_report(report, reports_dir, source.stem, write_outputs)

    mapping = detect_columns(frame, schema, header_row_index=header_row, sheet_name=sheet_name)
    mapped = apply_mapping(frame, mapping, constant_columns=config.constant_columns)
    mapped.insert(0, "_source_row", range(1, len(mapped) + 1))

    standardised, transformations, invalid_parses = standardise_frame(mapped, schema, config)
    issues, dup_summary, drop_mask, exclusion_reasons = validate(
        standardised,
        schema,
        config,
        mapping_missing=mapping.missing_canonical_fields,
        invalid_parses=invalid_parses,
        constants_applied=list(config.constant_columns),
    )
    kept = standardised.loc[~drop_mask] if drop_mask.any() else standardised
    outlier_summary, outlier_issue = detect_outliers(
        kept,
        config,
        source_rows=standardised["_source_row"],
    )
    if outlier_issue:
        issues.append(outlier_issue)

    clean = kept.copy().reset_index(drop=True)
    clean = _order_columns(clean)
    excluded = standardised.loc[drop_mask].copy()
    if not excluded.empty:
        excluded.insert(0, "exclusion_reason", exclusion_reasons.loc[excluded.index])
    blocking = any(issue.code in BLOCKING_CODES and issue.severity == Severity.CRITICAL for issue in issues)
    ready = analysis_ready(clean, blocking)
    capabilities = check_capabilities(clean if not clean.empty else kept, config, ready=ready)

    drop_rate = (len(standardised) - len(clean)) / len(standardised) if len(standardised) else 1.0
    critical = [issue for issue in issues if issue.severity == Severity.CRITICAL]
    warnings = [issue for issue in issues if issue.severity == Severity.WARNING]
    info = [issue for issue in issues if issue.severity == Severity.INFO]
    sparse = any(issue.code == "SPARSE_HISTORY" for issue in warnings)
    status = _status(
        ready=ready,
        blocking=blocking,
        warnings=warnings,
        critical=critical,
        drop_rate=drop_rate,
        partial_threshold=config.row_drop_partial_threshold,
    )
    score = _quality_score(
        ready=ready,
        critical_count=len(critical),
        warning_count=len(warnings),
        drop_rate=drop_rate,
        outlier_rows=outlier_summary.total_flagged_rows,
        row_count=len(standardised),
        sparse=sparse,
    )

    missing_counts = {
        col: int(standardised[col].isna().sum())
        for col in CANONICAL_OUTPUT_ORDER
        if col in standardised.columns and int(standardised[col].isna().sum()) > 0
    }
    reason_counts: dict[str, int] = {}
    if not excluded.empty:
        for reason in excluded["exclusion_reason"].astype(str):
            for code in reason.split(";"):
                if code:
                    reason_counts[code] = reason_counts.get(code, 0) + 1

    if "date" in standardised.columns:
        dates = pd.to_datetime(standardised["date"], errors="coerce")
    else:
        dates = pd.Series(dtype="datetime64[ns]")
    valid_dates = dates.dropna()
    date_min = valid_dates.min().strftime("%Y-%m-%d") if not valid_dates.empty else None
    date_max = valid_dates.max().strftime("%Y-%m-%d") if not valid_dates.empty else None

    clean_path: Path | None = None
    exclusions_path: Path | None = None
    if write_outputs:
        if not clean.empty:
            clean_path = clean_dir / f"{source.stem}.clean.csv"
            _write_clean_csv(clean, clean_path)
            logger.info("clean_written path=%s rows=%s", clean_path, len(clean))
        if not excluded.empty:
            exclusions_path = reports_dir / f"{source.stem}.exclusions.csv"
            exclusions_path.parent.mkdir(parents=True, exist_ok=True)
            export_ex = excluded.copy()
            if "date" in export_ex.columns:
                export_ex["date"] = pd.to_datetime(export_ex["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            export_ex.to_csv(exclusions_path, index=False)
            logger.info("exclusions_written path=%s rows=%s", exclusions_path, len(export_ex))

    report = QAReport(
        status=status,
        analysis_ready=ready,
        quality_score=score,
        critical_issues=critical,
        warnings=warnings,
        info=info,
        capabilities=capabilities,
        column_mapping=mapping.source_to_canonical,
        unmapped_columns=mapping.unmapped_source_columns,
        missing_canonical_fields=mapping.missing_canonical_fields,
        missing_value_counts=missing_counts,
        outliers=outlier_summary if outlier_summary.columns else OutlierSummary(),
        duplicates=dup_summary,
        transformations=transformations,
        row_count_raw=len(standardised),
        row_count_clean=len(clean),
        rows_dropped=len(standardised) - len(clean),
        distinct_dates=distinct_dates(standardised),
        date_min=date_min,
        date_max=date_max,
        invalid_date_count=int(invalid_parses.get("date", 0)),
        numeric_parse_failures={k: v for k, v in invalid_parses.items() if v},
        source_columns=list(frame.columns),
        header_row_index=mapping.header_row_index,
        sheet_name=mapping.sheet_name,
        input_file=_display_path(source),
        raw_preserved_at=_display_path(raw_copy),
        clean_output_path=_display_path(clean_path) if clean_path else None,
        exclusions_output_path=_display_path(exclusions_path) if exclusions_path else None,
        exclusion_reason_counts=reason_counts,
    )
    return _persist_report(report, reports_dir, source.stem, write_outputs)


def _persist_report(report: QAReport, reports_dir: Path, stem: str, write_outputs: bool) -> QAReport:
    if not write_outputs:
        return report
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{stem}.qa.json"
    report.report_output_path = _display_path(path)
    path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
    logger.info("report_written path=%s status=%s", path, report.status.value)
    return report
