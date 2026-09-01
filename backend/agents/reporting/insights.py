"""Summarise a cleaned POS table for the Report Agent. Deterministic — no LLM."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class RankedShare(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float
    share: float


class CommercialSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_data: bool
    row_count: int = 0
    total_value: float = 0.0
    total_volume: float = 0.0
    n_products: int = 0
    n_manufacturers: int = 0
    n_retailers: int = 0
    n_regions: int = 0
    n_dates: int = 0
    date_min: str | None = None
    date_max: str | None = None
    top_manufacturers: list[RankedShare] = Field(default_factory=list)
    top_products: list[RankedShare] = Field(default_factory=list)
    top_retailers: list[RankedShare] = Field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _ranked(frame: pd.DataFrame, column: str, value_col: str, limit: int = 8) -> list[RankedShare]:
    if column not in frame.columns or value_col not in frame.columns:
        return []
    working = frame[[column, value_col]].copy()
    working[column] = working[column].fillna("Unknown").astype(str)
    grouped = working.groupby(column, dropna=False)[value_col].sum().sort_values(ascending=False)
    total = float(grouped.sum())
    rows: list[RankedShare] = []
    for name, value in grouped.head(limit).items():
        share = float(value / total) if total else 0.0
        rows.append(RankedShare(name=str(name), value=float(value), share=share))
    return rows


def _nunique(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(frame[column].dropna().astype(str).nunique())


def build_snapshot(frame: pd.DataFrame) -> CommercialSnapshot:
    if frame is None or frame.empty:
        return CommercialSnapshot(has_data=False)

    if "sales_value" in frame.columns:
        value = pd.to_numeric(frame["sales_value"], errors="coerce")
    else:
        value = pd.Series(dtype=float)
    if "sales_volume" in frame.columns:
        volume = pd.to_numeric(frame["sales_volume"], errors="coerce")
    else:
        volume = pd.Series(dtype=float)
    if "date" in frame.columns:
        dates = pd.to_datetime(frame["date"], errors="coerce")
    else:
        dates = pd.Series(dtype="datetime64[ns]")
    valid_dates = dates.dropna()

    return CommercialSnapshot(
        has_data=True,
        row_count=len(frame),
        total_value=float(value.fillna(0).sum()),
        total_volume=float(volume.fillna(0).sum()),
        n_products=_nunique(frame, "product") or _nunique(frame, "sku"),
        n_manufacturers=_nunique(frame, "manufacturer"),
        n_retailers=_nunique(frame, "retailer"),
        n_regions=_nunique(frame, "region"),
        n_dates=int(valid_dates.nunique()) if not valid_dates.empty else 0,
        date_min=valid_dates.min().strftime("%Y-%m-%d") if not valid_dates.empty else None,
        date_max=valid_dates.max().strftime("%Y-%m-%d") if not valid_dates.empty else None,
        top_manufacturers=_ranked(frame, "manufacturer", "sales_value"),
        top_products=_ranked(frame, "product", "sales_value"),
        top_retailers=_ranked(frame, "retailer", "sales_value"),
    )
