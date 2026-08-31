"""Pydantic models and configuration for the Data QA Agent."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_SCHEMA_PATH = SCHEMA_DIR / "canonical_schema.yaml"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "qa_config.yaml"


class Status(StrEnum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    PARTIAL_PASS = "PARTIAL_PASS"
    FAIL = "FAIL"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class FieldRole(StrEnum):
    DIMENSION = "dimension"
    METRIC = "metric"
    PRICE = "price"
    PROMOTION = "promotion"


class FieldDtype(StrEnum):
    DATE = "date"
    TEXT = "text"
    NUMBER = "number"
    PERCENT = "percent"
    FLAG = "flag"


class CanonicalField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: FieldRole
    dtype: FieldDtype
    required_for: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class CanonicalSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[CanonicalField]

    def by_name(self) -> dict[str, CanonicalField]:
        return {field.name: field for field in self.fields}

    def required_for_basic(self) -> list[CanonicalField]:
        return [field for field in self.fields if "basic" in field.required_for]


class OutlierConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = "mad"
    mad_threshold: float = 3.5
    iqr_multiplier: float = 1.5
    min_observations: int = 8


class QAConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invalid_date_rate_threshold: float = 0.05
    invalid_numeric_rate_threshold: float = 0.05
    required_null_rate_threshold: float = 0.50
    row_drop_partial_threshold: float = 0.05
    min_history_periods: int = 8
    min_history_for_price_agent: int = 8
    min_history_for_promo_agent: int = 8
    header_scan_rows: int = 30
    min_header_alias_matches: int = 2
    outlier: OutlierConfig = Field(default_factory=OutlierConfig)
    duplicate_key_fields: list[str] = Field(
        default_factory=lambda: ["date", "retailer", "manufacturer", "sku", "product", "region"]
    )
    constant_columns: dict[str, str] = Field(default_factory=dict)
    text_case: dict[str, str] = Field(default_factory=dict)
    date_formats: list[str] = Field(default_factory=list)


class QAIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Severity
    message: str
    column: str | None = None
    row_count: int = 0
    sample_values: list[str] = Field(default_factory=list)


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distribution: bool
    price: bool
    promotion: bool
    macro_overlay: bool
    social_evidence: bool
    commercial_brain: bool


class OutlierColumnSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    method: str
    count: int
    sample_source_rows: list[int] = Field(default_factory=list)


class OutlierSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_flagged_rows: int = 0
    columns: list[OutlierColumnSummary] = Field(default_factory=list)


class DuplicateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_fields: list[str] = Field(default_factory=list)
    duplicate_row_count: int = 0
    unsafe_group_count: int = 0
    safely_dropped: int = 0


class ColumnMappingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_to_canonical: dict[str, str]
    canonical_to_source: dict[str, str]
    unmapped_source_columns: list[str]
    missing_canonical_fields: list[str]
    header_row_index: int
    sheet_name: str | None = None


class Transformation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    column: str | None = None
    row_count: int = 0


class QAReport(BaseModel):
    """Structured QA output consumed by downstream agents."""

    model_config = ConfigDict(extra="forbid")

    status: Status
    analysis_ready: bool
    quality_score: int = Field(ge=0, le=100)
    critical_issues: list[QAIssue] = Field(default_factory=list)
    warnings: list[QAIssue] = Field(default_factory=list)
    info: list[QAIssue] = Field(default_factory=list)
    capabilities: Capabilities
    column_mapping: dict[str, str] = Field(default_factory=dict)
    unmapped_columns: list[str] = Field(default_factory=list)
    missing_canonical_fields: list[str] = Field(default_factory=list)
    missing_value_counts: dict[str, int] = Field(default_factory=dict)
    outliers: OutlierSummary = Field(default_factory=OutlierSummary)
    duplicates: DuplicateSummary = Field(default_factory=DuplicateSummary)
    transformations: list[Transformation] = Field(default_factory=list)
    row_count_raw: int = 0
    row_count_clean: int = 0
    rows_dropped: int = 0
    distinct_dates: int = 0
    date_min: str | None = None
    date_max: str | None = None
    invalid_date_count: int = 0
    numeric_parse_failures: dict[str, int] = Field(default_factory=dict)
    source_columns: list[str] = Field(default_factory=list)
    header_row_index: int = 0
    sheet_name: str | None = None
    input_file: str
    raw_preserved_at: str
    clean_output_path: str | None = None
    report_output_path: str | None = None
    exclusions_output_path: str | None = None
    exclusion_reason_counts: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"YAML at {path} must be a mapping")
    return payload


def load_canonical_schema(path: Path | None = None) -> CanonicalSchema:
    payload = _read_yaml(path or DEFAULT_SCHEMA_PATH)
    raw_fields = payload.get("fields", {})
    fields: list[CanonicalField] = []
    if isinstance(raw_fields, dict):
        for name, spec in raw_fields.items():
            fields.append(CanonicalField(name=name, **spec))
    elif isinstance(raw_fields, list):
        fields = [CanonicalField(**item) for item in raw_fields]
    else:
        raise TypeError("canonical schema 'fields' must be a mapping or list")
    return CanonicalSchema(fields=fields)


def load_qa_config(path: Path | None = None) -> QAConfig:
    payload = _read_yaml(path or DEFAULT_CONFIG_PATH)
    return QAConfig.model_validate(payload)
