"""Load sourced macro catalogs. Agents consume these files; they do not invent series."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.agents.macro_common.models import MacroCatalog

AGENT_CATALOG_FILES = {
    "InflationCostAgent": "inflation_cost.json",
    "ConsumerRetailAgent": "consumer_retail.json",
    "RatesFXAgent": "rates_fx.json",
    "EnergyCommodityAgent": "energy_commodity.json",
}

AGENT_REPORT_FILES = {
    "InflationCostAgent": "inflation_cost_v1.json",
    "ConsumerRetailAgent": "consumer_retail_v1.json",
    "RatesFXAgent": "rates_fx_v1.json",
    "EnergyCommodityAgent": "energy_commodity_v1.json",
}

AGENT_REPORT_DIRS = {
    "InflationCostAgent": "macro_inflation_reports",
    "ConsumerRetailAgent": "macro_consumer_reports",
    "RatesFXAgent": "macro_rates_reports",
    "EnergyCommodityAgent": "energy_commodity_reports",
}


class MacroLoadError(ValueError):
    """Macro catalog or Commercial Brain input cannot be used."""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def data_root_for(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_dir():
        if path.name == "macro_observations":
            return path.parent
        return path
    if path.parent.name in {
        "macro_observations",
        "brain_reports",
        "storytelling_reports",
        "macro_context",
        "macro_inflation_reports",
        "macro_consumer_reports",
        "macro_rates_reports",
        "energy_commodity_reports",
        "macro_brain_reports",
    }:
        return path.parent.parent
    return path.parent


def read_json_object(path: Path, *, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MacroLoadError(f"Cannot read {kind} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MacroLoadError(f"{path} is not a JSON object")
    return payload


def load_catalog(path: Path) -> MacroCatalog:
    payload = read_json_object(path, kind="macro observation catalog")
    try:
        return MacroCatalog.model_validate(payload)
    except Exception as exc:
        raise MacroLoadError(f"Invalid macro catalog {path}: {exc}") from exc


def discover_catalog(path: Path, agent: str) -> Path:
    path = path.expanduser().resolve()
    filename = AGENT_CATALOG_FILES[agent]
    if path.is_file():
        return path
    named = [
        path / "macro_observations" / filename,
        path / filename,
    ]
    for item in named:
        if item.is_file():
            return item
    raise MacroLoadError(f"No {agent} catalog found under {path} (expected macro_observations/{filename})")


def report_dir_for(data_root: Path, agent: str) -> Path:
    return data_root / AGENT_REPORT_DIRS[agent]
