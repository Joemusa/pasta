"""MoM/YoY/direction from sourced points. Missing stays None; never coerced to zero."""

from __future__ import annotations

from datetime import date

from backend.agents.macro_common.models import MacroConfig, ObservationPoint, SeriesDefinition


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def sort_points(points: list[ObservationPoint]) -> list[ObservationPoint]:
    dated = [item for item in points if parse_iso_date(item.observation_date) is not None]
    undated = [item for item in points if parse_iso_date(item.observation_date) is None]
    dated.sort(key=lambda item: parse_iso_date(item.observation_date) or date.min)
    return dated + undated


def subtract(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def percent_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current / previous - 1.0) * 100.0


def latest_and_previous(
    points: list[ObservationPoint],
) -> tuple[ObservationPoint | None, ObservationPoint | None, ObservationPoint | None]:
    ordered = sort_points(points)
    dated = [item for item in ordered if parse_iso_date(item.observation_date) is not None]
    if not dated:
        if not ordered:
            return None, None, None
        current = ordered[-1]
        previous = ordered[-2] if len(ordered) >= 2 else None
        return current, previous, None
    current = dated[-1]
    previous = dated[-2] if len(dated) >= 2 else None
    current_date = parse_iso_date(current.observation_date)
    year_ago = None
    if current_date is not None:
        target = date(current_date.year - 1, current_date.month, current_date.day)
        matches = [item for item in dated[:-1] if parse_iso_date(item.observation_date) == target]
        if matches:
            year_ago = matches[-1]
    return current, previous, year_ago


def metric_direction(change: float | None, *, tolerance: float = 1e-12) -> str:
    if change is None:
        return "INSUFFICIENT"
    if abs(change) <= tolerance:
        return "UNCHANGED"
    return "UP" if change > 0 else "DOWN"


def commercial_pressure(direction: str, higher_is: str) -> str:
    if direction == "INSUFFICIENT":
        return "INSUFFICIENT"
    if direction == "UNCHANGED":
        return "NEUTRAL"
    tighter_when_up = higher_is in {
        "tighter_consumer",
        "tighter_manufacturer",
        "tighter_import",
        "tighter_retailer",
        "higher_cost",
    }
    easier_when_up = higher_is in {
        "easier_consumer",
        "easier_manufacturer",
        "stronger_demand",
        "stronger_confidence",
    }
    if tighter_when_up:
        return "TIGHTENING" if direction == "UP" else "EASING"
    if easier_when_up:
        return "EASING" if direction == "UP" else "TIGHTENING"
    return "NEUTRAL"


def signal_strength(change: float | None, series: SeriesDefinition, config: MacroConfig) -> str:
    if change is None:
        return "LOW"
    magnitude = abs(change)
    thresholds = config.signal_strength or {}
    unit = series.unit.lower()
    if unit in {"index_point", "index"}:
        high = float(thresholds.get("index_point_high", 5.0))
        medium = float(thresholds.get("index_point_medium", 2.0))
    elif unit in {"zar_per_usd"}:
        high = float(thresholds.get("fx_high", 0.5))
        medium = float(thresholds.get("fx_medium", 0.1))
    elif unit in {"usd_per_barrel"}:
        high = float(thresholds.get("usd_high", 5.0))
        medium = float(thresholds.get("usd_medium", 2.0))
    elif unit in {"cents_per_litre"}:
        high = float(thresholds.get("cents_high", 50.0))
        medium = float(thresholds.get("cents_medium", 20.0))
    else:
        high = float(thresholds.get("percent_high", 0.5))
        medium = float(thresholds.get("percent_medium", 0.2))
    if magnitude >= high:
        return "HIGH"
    if magnitude >= medium:
        return "MEDIUM"
    return "LOW"


def observation_confidence(
    *,
    current: ObservationPoint,
    previous_value: float | None,
    source: str,
) -> str:
    official = any(
        token in source.lower()
        for token in (
            "statistics south africa",
            "south african reserve bank",
            "bureau for economic research",
            "department of mineral",
            "national treasury",
            "south african government",
        )
    )
    if current.value is None or current.observation_date is None:
        return "LOW"
    if not official:
        return "LOW"
    if current.publication_date is None or previous_value is None:
        return "MEDIUM"
    return "HIGH"
