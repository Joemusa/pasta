"""Builders for specialist macro-agent tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_catalog(root: Path, agent: str, series: list[dict], filename: str) -> Path:
    path = root / "macro_observations" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agent": agent,
        "version": "V1",
        "retrieved_at": "2026-08-31",
        "notes": [],
        "series": series,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def series(
    metric: str,
    observations: list[dict],
    *,
    unit: str = "percent_yoy",
    frequency: str = "monthly",
    source: str = "Statistics South Africa",
    source_url: str = "https://www.statssa.gov.za/",
    fmcg_relevance: str = "HIGH",
    commercial_levers: list[str] | None = None,
    fmcg_channels: list[str] | None = None,
    higher_is: str = "tighter_consumer",
    value_is_period_change: bool = False,
) -> dict:
    item = {
        "metric": metric,
        "unit": unit,
        "frequency": frequency,
        "date_convention": "month_end",
        "source": source,
        "source_url": source_url,
        "fmcg_relevance": fmcg_relevance,
        "commercial_levers": commercial_levers or ["PRICE"],
        "fmcg_channels": fmcg_channels or ["CONSUMER_AFFORDABILITY"],
        "higher_is": higher_is,
        "observations": observations,
    }
    if value_is_period_change:
        item["value_is_period_change"] = True
    return item
