"""Align macro observation dates to the POS window. Future observations do not explain POS."""

from __future__ import annotations

from backend.agents.macro_common.calc import parse_iso_date
from backend.agents.macro_common.models import MacroConfig, ObservationPoint, SeriesDefinition


def align_observation(
    current: ObservationPoint,
    series: SeriesDefinition,
    config: MacroConfig,
) -> tuple[str, str]:
    pos_start = parse_iso_date(config.pos_period_start)
    pos_end = parse_iso_date(config.pos_period_end)
    observed = parse_iso_date(current.observation_date)
    published = parse_iso_date(current.publication_date)
    convention = series.date_convention

    if observed is None:
        return "observation_date_not_supplied", "INSUFFICIENT_DATES"
    if pos_end is None or pos_start is None:
        return convention, "INSUFFICIENT_DATES"
    if observed > pos_end:
        return f"{convention}; observation_after_pos_period_end", "FUTURE_LEAKAGE"
    if published is None:
        return f"{convention}; latest_observation_on_or_before_pos_period_end", "ALIGNED_OBSERVATION_ONLY"
    if published > pos_end:
        return (
            f"{convention}; observation_on_or_before_pos_period_end; publication_after_pos_period_end",
            "ALIGNED_WITH_PUBLICATION_LAG",
        )
    return f"{convention}; observation_and_publication_on_or_before_pos_period_end", "ALIGNED"
