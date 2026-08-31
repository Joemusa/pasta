"""Map source column names onto the canonical commercial schema."""

from __future__ import annotations

import logging
import re

import pandas as pd

from backend.agents.data_qa.models import CanonicalSchema, ColumnMappingResult

logger = logging.getLogger("backend.agents.data_qa.schema_detector")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(value: str) -> str:
    text = str(value).strip().lower()
    text = text.replace("%", " percent ")
    text = _NON_ALNUM.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def alias_index(schema: CanonicalSchema) -> dict[str, str]:
    """Normalized alias -> canonical field name. First alias wins on collision."""
    index: dict[str, str] = {}
    for field in schema.fields:
        tokens = [field.name, *field.aliases]
        for token in tokens:
            key = normalize_name(token)
            if not key:
                continue
            index.setdefault(key, field.name)
    return index


def detect_columns(
    frame: pd.DataFrame,
    schema: CanonicalSchema,
    header_row_index: int = 0,
    sheet_name: str | None = None,
) -> ColumnMappingResult:
    index = alias_index(schema)
    source_to_canonical: dict[str, str] = {}
    canonical_to_source: dict[str, str] = {}
    unmapped: list[str] = []
    collisions: list[str] = []

    for source in frame.columns:
        key = normalize_name(str(source))
        canonical = index.get(key)
        if canonical is None:
            unmapped.append(str(source))
            continue
        if canonical in canonical_to_source:
            collisions.append(
                f"{source}->{canonical} already mapped from {canonical_to_source[canonical]}"
            )
            unmapped.append(str(source))
            continue
        source_to_canonical[str(source)] = canonical
        canonical_to_source[canonical] = str(source)

    missing = [field.name for field in schema.fields if field.name not in canonical_to_source]
    if collisions:
        logger.warning("mapping_collisions %s", collisions)
    logger.info(
        "schema_mapped mapped=%s unmapped=%s missing=%s",
        source_to_canonical,
        unmapped,
        missing,
    )
    return ColumnMappingResult(
        source_to_canonical=source_to_canonical,
        canonical_to_source=canonical_to_source,
        unmapped_source_columns=unmapped,
        missing_canonical_fields=missing,
        header_row_index=header_row_index,
        sheet_name=sheet_name,
    )


def apply_mapping(
    frame: pd.DataFrame,
    mapping: ColumnMappingResult,
    constant_columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Rename mapped columns; keep extras under original names; apply constants."""
    renamed = frame.rename(columns=mapping.source_to_canonical).copy()
    extras = [col for col in mapping.unmapped_source_columns if col in renamed.columns]
    for extra in extras:
        snake = normalize_name(extra).replace(" ", "_") or "extra"
        target = snake if snake not in renamed.columns else f"extra_{snake}"
        renamed = renamed.rename(columns={extra: target})
    constants = constant_columns or {}
    for field_name, value in constants.items():
        if field_name not in renamed.columns:
            renamed[field_name] = value
            logger.info("constant_column field=%s value=%s", field_name, value)
    return renamed
