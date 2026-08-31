"""Pydantic models and configuration for the Commercial Data Integration Layer."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_CONFIG_PATH = SCHEMA_DIR / "integration_config.yaml"

JOIN_KEY = ("product", "retailer", "region", "date")

# Canonical columns and the exact source field each comes from.
# RSP columns are not labelled "normal price"; that meaning has not been proven.
FIELD_SOURCES: dict[str, str] = {
    "product": "join key: POS.product / price-promo.Product",
    "manufacturer": "POS.manufacturer, else price-promo.Manufacturer",
    "brand": "price-promo.Brand (cleaned POS has no brand column)",
    "retailer": "join key: POS.retailer / price-promo.Retailer",
    "region": "join key: POS.region / price-promo.Region",
    "date": "join key: POS.date / price-promo.DDMMMYY parsed with %d %b %y",
    "sales_value": "POS.sales_value",
    "sales_volume": "POS.sales_volume",
    "store_count": "POS.store_count",
    "pos_current_price": "POS.current_price (realised / average selling price from the POS extract)",
    "off_promo_price": "price-promo '4 Weeks CY Ave Price Quantity' where Promotion Indicator = 0",
    "on_promo_price": "price-promo '4 Weeks CY Ave Price Quantity' where Promotion Indicator = 1",
    "off_promo_rsp": (
        "price-promo '4 Weeks CY Ave RSP On Promo' where Promotion Indicator = 0 "
        "(not proven as normal shelf price)"
    ),
    "on_promo_rsp": (
        "price-promo '4 Weeks CY Ave RSP On Promo' where Promotion Indicator = 1 "
        "(not proven as normal shelf price)"
    ),
    "off_promo_sales": "price-promo '4 Weeks CY Sales On Promo' where Promotion Indicator = 0",
    "on_promo_sales": "price-promo '4 Weeks CY Sales On Promo' where Promotion Indicator = 1",
    "off_promo_time": "price-promo 'CY % Time On Promo' where Promotion Indicator = 0",
    "on_promo_time": "price-promo 'CY % Time On Promo' where Promotion Indicator = 1",
    "off_promo_sales_pct": "price-promo '4 Weeks CY % Sales On Promo' where Promotion Indicator = 0",
    "on_promo_sales_pct": "price-promo '4 Weeks CY % Sales On Promo' where Promotion Indicator = 1",
    "pos_percent_time_on_promo": "POS.percent_time_on_promo",
    "pos_percent_sales_on_promo": "POS.percent_sales_on_promo",
    "promotion_indicator_off_present": "true if a Promotion Indicator = 0 source row existed for the grain",
    "promotion_indicator_on_present": "true if a Promotion Indicator = 1 source row existed for the grain",
    "promotion_states": "sorted Promotion Indicator values observed at the grain (e.g. '0|1')",
    "productsid": (
        "pipe-separated distinct price-promo.ProductsID values at the grain "
        "(lineage only, not a join key)"
    ),
    "productsid_count": "number of distinct ProductsID values at the grain",
    "price_promo_source_rows": "raw price/promo rows collapsed into the grain",
    "pos_source_row": "POS._source_row",
    "in_pos": "true if a cleaned POS row exists for the grain",
    "in_price_promo": "true if a pivoted price/promo grain exists",
    "price_promo_available": "true if this grain matched the price/promotion source (row-level)",
    "flag_unmatched_pos": "POS grain with no price/promo grain",
    "flag_unmatched_price_promo": "price/promo grain with no POS grain",
    "flag_multiple_source_matches": (
        "more than one price/promo row per Promotion Indicator (typically multiple ProductsID)"
    ),
    "flag_missing_price": "pos_current_price, off_promo_price, and on_promo_price are all missing",
    "flag_missing_promotion_metrics": "all six pivoted off/on promo metric columns are missing",
    "flag_missing_rsp": "off_promo_rsp and on_promo_rsp are both missing",
    "flag_price_promo_unavailable_for_period": (
        "the row date does not exist in the price/promotion source calendar"
    ),
    "flag_ambiguous_product_mapping": "the product name maps to more than one ProductsID at this grain",
}


class IntegrationStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


class IntegrationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    join_key: list[str] = Field(default_factory=lambda: list(JOIN_KEY))
    promo_date_format: str = "%d %b %y"
    promo_date_column: str = "DDMMMYY"
    promotion_indicator_column: str = "Promotion Indicator"
    off_promo_indicator: int = 0
    on_promo_indicator: int = 1
    promo_columns: dict[str, str] = Field(default_factory=dict)
    pos_columns: dict[str, str] = Field(default_factory=dict)
    default_pos_path: str = "backend/data/clean/New Discovery_2026-08-27 (3).clean.csv"
    default_price_promo_path: str = "Unilever_Price_Promo_4weeks.csv"


class WeeklyCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    pos_records: int
    price_promo_records: int
    matched: int
    unmatched_pos: int
    unmatched_price_promo: int
    match_pct: float | None = None


class ProductMappingIssues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    productsid_to_one_product: bool = True
    ids_with_multiple_product_names: int = 0
    products_with_multiple_ids: int = 0
    products_with_multiple_ids_names: list[str] = Field(default_factory=list)
    pos_products_absent_from_price_promo: list[str] = Field(default_factory=list)
    canonical_grains_with_multiple_ids: int = 0
    note: str = (
        "ProductsID is not the join key. Each ProductsID maps to one product name; "
        "a product name may map to multiple ProductsID values."
    )


class IntegrationReport(BaseModel):
    """Structured output of the Commercial Data Integration Layer."""

    model_config = ConfigDict(extra="forbid")

    status: IntegrationStatus
    grain: list[str] = Field(default_factory=lambda: list(JOIN_KEY))
    join_key: list[str] = Field(default_factory=lambda: list(JOIN_KEY))
    pos_source_file: str
    price_promo_source_file: str
    canonical_output_path: str | None = None
    report_output_path: str | None = None
    pos_row_count: int = 0
    price_promo_row_count: int = 0
    price_promo_grain_count: int = 0
    canonical_row_count: int = 0
    overlapping_weeks: list[str] = Field(default_factory=list)
    non_overlapping_weeks: list[str] = Field(default_factory=list)
    match_rate_pos: float | None = None
    match_rate_unilever_pos: float | None = None
    match_rate_unilever_overlapping_weeks: float | None = None
    unmatched_pos_records: int = 0
    unmatched_price_promo_records: int = 0
    unmatched_price_promo_grains: int = 0
    matched_pos_records: int = 0
    promotion_multi_state_grains: int = 0
    multiple_source_match_grains: int = 0
    canonical_duplicate_rows: int = 0
    price_enabled_rows: int = 0
    promotion_enabled_rows: int = 0
    price_promo_available_rows: int = 0
    july_26_pos_rows_retained: int = 0
    product_mapping: ProductMappingIssues = Field(default_factory=ProductMappingIssues)
    weekly: list[WeeklyCoverage] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=lambda: dict(FIELD_SOURCES))
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"YAML at {path} must be a mapping")
    return payload


def load_integration_config(path: Path | None = None) -> IntegrationConfig:
    return IntegrationConfig.model_validate(_read_yaml(path or DEFAULT_CONFIG_PATH))
