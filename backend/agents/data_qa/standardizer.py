"""Standardise types, text, dates, percentages, and empty values."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

import pandas as pd

from backend.agents.data_qa.models import CanonicalSchema, FieldDtype, QAConfig, Transformation

logger = logging.getLogger("backend.agents.data_qa.standardizer")

_CURRENCY = re.compile(r"[Rr$€£¥,\s]")
_NULL_TOKENS = {
    "",
    "nan",
    "none",
    "null",
    "n/a",
    "na",
    "-",
    "--",
    "#n/a",
    "#na",
    "<na>",
    "<nat>",
}
_TRUE_TOKENS = {"1", "true", "yes", "y", "t", "on", "promo", "promoted"}
_FALSE_TOKENS = {"0", "false", "no", "n", "f", "off"}


def is_null_token(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip().lower()
    return text in _NULL_TOKENS


def empty_to_null(series: pd.Series) -> tuple[pd.Series, int]:
    mask = series.map(is_null_token)
    converted = series.where(~mask, other=pd.NA)
    if converted.dtype == object:
        converted = converted.map(lambda v: v.strip() if isinstance(v, str) else v)
    return converted, int(mask.sum())


def parse_number(value: Any) -> float:
    if is_null_token(value):
        return math.nan
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    text = text.replace("\u00a0", " ")
    text = _CURRENCY.sub("", text)
    text = text.replace("%", "")
    if is_null_token(text):
        return math.nan
    try:
        return float(text)
    except (TypeError, ValueError):
        return math.nan


def parse_flag(value: Any) -> Any:
    if is_null_token(value):
        return pd.NA
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(int(value))
        return pd.NA
    text = str(value).strip().lower()
    if text in _TRUE_TOKENS:
        return True
    if text in _FALSE_TOKENS:
        return False
    return pd.NA


def parse_dates(series: pd.Series, formats: list[str]) -> tuple[pd.Series, int, int]:
    """Return datetime64 series, parsed_count, invalid_count (non-null that failed)."""
    if pd.api.types.is_datetime64_any_dtype(series):
        valid = series.notna()
        return pd.to_datetime(series), int(valid.sum()), 0

    original_null = series.map(is_null_token)
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    remainder = ~original_null

    already_dt = remainder & series.map(lambda v: hasattr(v, "year") and not isinstance(v, str))
    if already_dt.any():
        parsed.loc[already_dt] = pd.to_datetime(series.loc[already_dt], errors="coerce")
        remainder = remainder & parsed.isna()
    excel_serial = pd.to_numeric(series.where(remainder), errors="coerce")
    serial_mask = remainder & excel_serial.between(200, 80000)
    if serial_mask.any():
        parsed.loc[serial_mask] = pd.to_datetime(
            excel_serial.loc[serial_mask],
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )
        remainder = remainder & parsed.isna()

    for fmt in formats:
        if not remainder.any():
            break
        attempt = pd.to_datetime(series.where(remainder), format=fmt, errors="coerce")
        ok = remainder & attempt.notna()
        parsed.loc[ok] = attempt.loc[ok]
        remainder = remainder & parsed.isna()

    if remainder.any():
        try:
            attempt = pd.to_datetime(series.where(remainder), errors="coerce", format="mixed")
        except (TypeError, ValueError):
            attempt = pd.to_datetime(series.where(remainder), errors="coerce")
        ok = remainder & attempt.notna()
        parsed.loc[ok] = attempt.loc[ok]
        remainder = remainder & parsed.isna()

    parsed_count = int((~original_null & parsed.notna()).sum())
    invalid_count = int(remainder.sum())
    return parsed, parsed_count, invalid_count


def _apply_text_case(value: Any, mode: str) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if mode == "preserve" or not text:
        return text
    if mode == "upper":
        return text.upper()
    if mode == "lower":
        return text.lower()
    if mode == "title":
        if text.isupper() or text.islower():
            return text.title()
        return text
    return text


def _standardise_percent(series: pd.Series) -> tuple[pd.Series, str | None, int]:
    numeric = series.map(lambda v: parse_number(v) if not is_null_token(v) else math.nan)
    numeric = pd.to_numeric(numeric, errors="coerce")
    present = numeric.dropna()
    if present.empty:
        return numeric, None, 0
    vmin = float(present.min())
    vmax = float(present.max())
    if vmin < 0:
        return numeric, None, int((numeric < 0).sum())
    if vmax <= 1.0:
        scaled = (numeric * 100.0).round(4)
        return scaled, "percent_scaled_0_1_to_0_100", int(present.shape[0])
    return numeric, None, 0


def standardise_frame(
    frame: pd.DataFrame,
    schema: CanonicalSchema,
    config: QAConfig,
) -> tuple[pd.DataFrame, list[Transformation], dict[str, int]]:
    """Return cleaned-types frame, transformations, and per-column invalid parse counts."""
    out = frame.copy()
    transformations: list[Transformation] = []
    invalid_parses: dict[str, int] = {}
    fields = schema.by_name()

    for column in list(out.columns):
        series, nulls = empty_to_null(out[column])
        if nulls:
            transformations.append(
                Transformation(
                    code="empty_to_null",
                    message=f"Converted {nulls} empty/placeholder values to null",
                    column=column,
                    row_count=nulls,
                )
            )
        out[column] = series

    for name, field in fields.items():
        if name not in out.columns:
            continue
        if field.dtype == FieldDtype.TEXT:
            mode = config.text_case.get(name, "preserve")
            before = out[name].copy()
            out[name] = out[name].map(lambda v, m=mode: _apply_text_case(v, m) if isinstance(v, str) else v)
            changed = int((before.fillna("__NA__") != out[name].fillna("__NA__")).sum())
            if changed:
                transformations.append(
                    Transformation(
                        code="text_standardised",
                        message=f"Trimmed/standardised text casing ({mode})",
                        column=name,
                        row_count=changed,
                    )
                )
        elif field.dtype == FieldDtype.DATE:
            parsed, parsed_count, invalid_count = parse_dates(out[name], config.date_formats)
            out[name] = parsed
            invalid_parses[name] = invalid_count
            transformations.append(
                Transformation(
                    code="dates_parsed",
                    message=f"Parsed {parsed_count} dates ({invalid_count} invalid)",
                    column=name,
                    row_count=parsed_count,
                )
            )
        elif field.dtype == FieldDtype.FLAG:
            out[name] = out[name].map(parse_flag)
            invalid = int(out[name].isna().sum() - frame[name].map(is_null_token).sum())
            if invalid < 0:
                invalid = int(out[name].isna().sum())
            invalid_parses[name] = max(invalid, 0)
        elif field.dtype == FieldDtype.PERCENT:
            scaled, code, count = _standardise_percent(out[name])
            out[name] = scaled
            if code:
                transformations.append(
                    Transformation(
                        code=code,
                        message="Detected 0-1 percentage scale and standardised to 0-100",
                        column=name,
                        row_count=count,
                    )
                )
        elif field.dtype == FieldDtype.NUMBER:
            coerced = out[name].map(lambda v: parse_number(v) if not is_null_token(v) else math.nan)
            coerced = pd.to_numeric(coerced, errors="coerce")
            original_non_null = ~out[name].map(is_null_token)
            failed = int((original_non_null & coerced.isna()).sum())
            invalid_parses[name] = failed
            out[name] = coerced
            transformations.append(
                Transformation(
                    code="numeric_coerced",
                    message=f"Coerced numeric values ({failed} invalid)",
                    column=name,
                    row_count=int(original_non_null.sum()),
                )
            )

    logger.info("standardise_ok transformations=%s", len(transformations))
    return out, transformations, invalid_parses
