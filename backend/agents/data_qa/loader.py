"""Load CSV and Excel uploads and detect the header row."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from backend.agents.data_qa.models import CanonicalSchema, QAConfig
from backend.agents.data_qa.schema_detector import alias_index, normalize_name

logger = logging.getLogger("backend.agents.data_qa.loader")

SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xlsm"}


class LoadError(Exception):
    """Raised when an upload cannot be read as a table."""


def inspect_file(path: Path) -> None:
    if not path.exists():
        raise LoadError(f"File does not exist: {path}")
    if not path.is_file():
        raise LoadError(f"Not a file: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise LoadError(
            f"Unsupported file type '{path.suffix}'. Supported: {sorted(SUPPORTED_SUFFIXES)}"
        )


def _read_csv(path: Path, header: int | None) -> pd.DataFrame:
    return pd.read_csv(path, header=header, dtype=object, keep_default_na=False)


def _excel_engine(_path: Path) -> str:
    return "openpyxl"


def _read_excel(
    path: Path,
    header: int | None,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame:
    return pd.read_excel(
        path,
        header=header,
        dtype=object,
        sheet_name=sheet_name if sheet_name is not None else 0,
        engine=_excel_engine(path),
        keep_default_na=False,
    )


def _sheet_names(path: Path) -> list[str]:
    engine = pd.ExcelFile(path, engine=_excel_engine(path))
    try:
        return list(engine.sheet_names)
    finally:
        engine.close()


def _row_alias_matches(values: list[object], aliases: set[str]) -> int:
    matches = 0
    seen: set[str] = set()
    for value in values:
        if value is None or value == "":
            continue
        token = normalize_name(str(value))
        if token and token in aliases and token not in seen:
            seen.add(token)
            matches += 1
    return matches


def detect_header_row(
    preview: pd.DataFrame,
    schema: CanonicalSchema,
    config: QAConfig,
) -> int:
    aliases = set(alias_index(schema).keys())
    best_row = 0
    best_matches = -1
    scan_rows = min(config.header_scan_rows, len(preview))
    for idx in range(scan_rows):
        values = preview.iloc[idx].tolist()
        matches = _row_alias_matches(values, aliases)
        if matches > best_matches:
            best_matches = matches
            best_row = idx
    if best_matches < config.min_header_alias_matches:
        logger.info(
            "header_fallback row=%s matches=%s",
            best_row,
            best_matches,
        )
        return 0
    logger.info("header_detected row=%s matches=%s", best_row, best_matches)
    return best_row


def _preview(path: Path, sheet_name: str | int, nrows: int) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(
            path,
            header=None,
            dtype=object,
            keep_default_na=False,
            nrows=nrows,
        )
    return pd.read_excel(
        path,
        header=None,
        dtype=object,
        sheet_name=sheet_name,
        engine=_excel_engine(path),
        keep_default_na=False,
        nrows=nrows,
    )


def _choose_sheet(path: Path, schema: CanonicalSchema, config: QAConfig) -> str:
    names = _sheet_names(path)
    if not names:
        raise LoadError(f"Excel workbook has no sheets: {path}")
    aliases = set(alias_index(schema).keys())
    best_name = names[0]
    best_matches = -1
    for name in names:
        preview = _preview(path, name, config.header_scan_rows)
        for idx in range(len(preview)):
            matches = _row_alias_matches(preview.iloc[idx].tolist(), aliases)
            if matches > best_matches:
                best_matches = matches
                best_name = name
    logger.info("sheet_selected name=%s matches=%s", best_name, best_matches)
    return best_name


def load_table(
    path: Path,
    schema: CanonicalSchema,
    config: QAConfig,
) -> tuple[pd.DataFrame, int, str | None]:
    """Return (frame, header_row_index, sheet_name). Columns are source names."""
    inspect_file(path)
    sheet_name: str | None = None
    try:
        if path.suffix.lower() == ".csv":
            preview = _preview(path, 0, config.header_scan_rows)
            header_row = detect_header_row(preview, schema, config)
            frame = _read_csv(path, header=header_row)
        else:
            sheet_name = _choose_sheet(path, schema, config)
            preview = _preview(path, sheet_name, config.header_scan_rows)
            header_row = detect_header_row(preview, schema, config)
            frame = _read_excel(path, header=header_row, sheet_name=sheet_name)
    except LoadError:
        raise
    except Exception as exc:
        raise LoadError(f"File cannot be read: {path} ({exc})") from exc

    frame = frame.copy()
    frame.columns = [str(col).strip() if str(col) != "nan" else f"unnamed_{i}" for i, col in enumerate(frame.columns)]
    # Drop fully empty rows created by title blocks below the header.
    nonempty = frame.apply(
        lambda row: any(str(v).strip() != "" and str(v).lower() != "nan" for v in row),
        axis=1,
    )
    frame = frame.loc[nonempty].reset_index(drop=True)
    if frame.empty:
        raise LoadError(f"File contains no data rows: {path}")
    logger.info(
        "load_ok path=%s rows=%s cols=%s header_row=%s sheet=%s",
        path,
        len(frame),
        list(frame.columns),
        header_row,
        sheet_name,
    )
    return frame, header_row, sheet_name
