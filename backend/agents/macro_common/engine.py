"""Turn a sourced catalog into a specialist macro report. POS values are not recalculated."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from backend.agents.macro_common.alignment import align_observation
from backend.agents.macro_common.calc import (
    commercial_pressure,
    latest_and_previous,
    metric_direction,
    observation_confidence,
    signal_strength,
    subtract,
)
from backend.agents.macro_common.catalog import (
    AGENT_REPORT_FILES,
    MacroLoadError,
    data_root_for,
    discover_catalog,
    display_path,
    load_catalog,
    report_dir_for,
)
from backend.agents.macro_common.language import assert_no_causal_language
from backend.agents.macro_common.models import (
    MacroAgentReport,
    MacroAgentStatus,
    MacroConfig,
    MacroObservation,
    MacroSignal,
    SeriesDefinition,
    load_macro_config,
)

logger = logging.getLogger("backend.agents.macro")


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def build_observation(series: SeriesDefinition, config: MacroConfig) -> MacroObservation | None:
    current, previous, year_ago = latest_and_previous(series.observations)
    if current is None:
        return None
    previous_value = previous.value if previous is not None else current.previous_value
    year_ago_value = year_ago.value if year_ago is not None else None
    mom_change = subtract(current.value, previous_value)
    yoy_change = subtract(current.value, year_ago_value)
    if series.unit == "percent_yoy" and year_ago is None and current.value is not None:
        # The published figure is already a year-on-year rate; do not invent a year-ago rate.
        yoy_change = current.value
    if mom_change is None and series.value_is_period_change:
        mom_change = current.value
    direction = metric_direction(mom_change)
    pressure = commercial_pressure(direction, series.higher_is)
    method, status = align_observation(current, series, config)
    confidence = observation_confidence(current=current, previous_value=previous_value, source=series.source)
    if status == "FUTURE_LEAKAGE":
        confidence = "LOW"
    return MacroObservation(
        metric=series.metric,
        value=current.value,
        previous_value=previous_value,
        year_ago_value=year_ago_value,
        mom_change=mom_change,
        yoy_change=yoy_change,
        direction=direction,  # type: ignore[arg-type]
        signal_strength=signal_strength(mom_change, series, config),  # type: ignore[arg-type]
        fmcg_relevance=series.fmcg_relevance,
        commercial_levers=list(series.commercial_levers),
        fmcg_channels=list(series.fmcg_channels),
        commercial_pressure=pressure,  # type: ignore[arg-type]
        source=series.source,
        source_url=series.source_url,
        publication_date=current.publication_date,
        observation_date=current.observation_date,
        confidence=confidence,  # type: ignore[arg-type]
        unit=series.unit,
        frequency=series.frequency,
        pos_period_start=config.pos_period_start,
        pos_period_end=config.pos_period_end,
        alignment_method=method,
        alignment_status=status,  # type: ignore[arg-type]
    )


def _signal_from_group(name: str, rows: list[MacroObservation]) -> MacroSignal:
    primary = max(rows, key=lambda item: (item.fmcg_relevance == "HIGH", item.signal_strength == "HIGH"))
    summary = (
        f"{primary.metric} is {primary.value} {primary.unit} "
        f"({primary.direction.lower()} vs previous; {primary.commercial_pressure.lower()} commercial pressure)."
        if primary.value is not None
        else f"{primary.metric} is missing a sourced value."
    )
    levers: list[str] = []
    channels: list[str] = []
    for row in rows:
        for lever in row.commercial_levers:
            if lever not in levers:
                levers.append(lever)
        for channel in row.fmcg_channels:
            if channel not in channels:
                channels.append(channel)
    return MacroSignal(
        name=name,
        summary=summary,
        direction=primary.direction,
        signal_strength=primary.signal_strength,
        fmcg_relevance=primary.fmcg_relevance,
        commercial_levers=levers,
        fmcg_channels=channels,
        commercial_pressure=primary.commercial_pressure,
        metrics=[row.metric for row in rows],
        alignment_status=primary.alignment_status,
        confidence=primary.confidence,
    )


def default_implications(agent: str, observations: list[MacroObservation]) -> list[str]:
    usable = [
        item
        for item in observations
        if item.alignment_status != "FUTURE_LEAKAGE" and item.value is not None
    ]
    if agent == "InflationCostAgent":
        food = next((item for item in usable if item.metric == "FOOD_CPI_YOY"), None)
        fuel = next((item for item in usable if item.metric == "FUEL_CPI_YOY"), None)
        headline = next((item for item in usable if item.metric == "HEADLINE_CPI_YOY"), None)
        lines = [
            "Headline consumer inflation eased in the latest sourced print, but that does not recalculate POS gaps."
        ]
        if food is not None and food.value is not None:
            lines.append(
                f"Food CPI is {food.value}% year-on-year, which is relevant to FMCG price architecture without "
                "claiming a causal POS effect."
            )
        if fuel is not None and fuel.value is not None:
            lines.append(
                f"Fuel CPI remains elevated at {fuel.value}% year-on-year, keeping household budgets value-conscious "
                "and raising the importance of availability."
            )
        if headline is not None and headline.commercial_pressure == "EASING":
            lines.append(
                "Softer headline inflation is supporting context for PRICE tests, not a substitute for distribution "
                "actions where store gaps already exist."
            )
        return lines
    if agent == "ConsumerRetailAgent":
        return [
            "Consumers are likely to remain value-conscious, increasing the importance of availability and targeted "
            "price/promotion execution.",
            "The FNB/BER CCI reading is retained as sourced evidence. "
            "It does not cause the POS distribution gaps.",
            "Weak household consumption and softer retailer confidence add context "
            "for retailer pressure, not a new action.",
        ]
    if agent == "RatesFXAgent":
        return [
            "A restrictive SARB policy rate is relevant to CONSUMER_AFFORDABILITY and RETAILER_PRESSURE.",
            "A slightly weaker rand in the official fuel-review window is relevant to IMPORT_COST and PRICE.",
            "Rate and FX context does not change POS opportunity values or create a new commercial action.",
        ]
    if agent == "EnergyCommodityAgent":
        return [
            "Brent eased in the official review window while diesel pump adjustments rose, so energy context is mixed.",
            "Fuel costs are relevant to MANUFACTURER_COST, IMPORT_COST and retailer logistics, not a POS rescore.",
            "Only commodities with a documented FMCG link and a source URL are included.",
        ]
    return ["Macro observations are supporting context only."]


def data_gaps(observations: list[MacroObservation]) -> list[str]:
    gaps: list[str] = []
    for item in observations:
        if item.value is None:
            gaps.append(f"{item.metric}: sourced value is missing and was not converted to zero.")
        if item.previous_value is None:
            gaps.append(f"{item.metric}: previous_value is missing.")
        if item.mom_change is None:
            gaps.append(f"{item.metric}: mom_change is null because a previous sourced print is missing.")
        if item.yoy_change is None:
            gaps.append(f"{item.metric}: year-ago value was not sourced; yoy_change is null.")
        if item.observation_date is None:
            gaps.append(f"{item.metric}: observation_date was not supplied by the source.")
        if item.alignment_status == "FUTURE_LEAKAGE":
            gaps.append(f"{item.metric}: observation is after the POS period and is not used to explain POS.")
        if item.alignment_status == "ALIGNED_WITH_PUBLICATION_LAG":
            gaps.append(f"{item.metric}: publication date is after the POS period (observation still precedes POS).")
    return gaps


def build_report(
    *,
    agent: str,
    catalog_path,
    config: MacroConfig,
) -> MacroAgentReport:
    catalog = load_catalog(catalog_path)
    if catalog.agent != agent:
        raise MacroLoadError(f"Catalog agent {catalog.agent!r} does not match {agent!r}")
    observations = [row for series in catalog.series if (row := build_observation(series, config)) is not None]
    grouped: dict[str, list[MacroObservation]] = defaultdict(list)
    for item in observations:
        grouped[item.metric.split("_")[0]].append(item)
    signals = [_signal_from_group(name, rows) for name, rows in grouped.items()]
    implications = default_implications(agent, observations)
    notes = list(config.limitations)
    notes.extend(catalog.notes)
    if any(item.alignment_status == "ALIGNED_WITH_PUBLICATION_LAG" for item in observations):
        notes.append("Some official releases were published after the POS week ended; they are labelled as such.")
    sources = sorted({item.source for item in observations})
    assert_no_causal_language(
        [
            *implications,
            *notes,
            *[item.summary for item in signals],
        ],
        config,
    )
    status = MacroAgentStatus.NOT_READY
    if observations:
        status = (
            MacroAgentStatus.READY_WITH_WARNINGS
            if data_gaps(observations)
            else MacroAgentStatus.READY
        )
    return MacroAgentReport(
        agent=agent,
        status=status,
        pos_period_start=config.pos_period_start,
        pos_period_end=config.pos_period_end,
        catalog_path=display_path(catalog_path),
        observations=observations,
        signals=signals,
        commercial_implications=implications,
        limitations=notes,
        data_gaps=data_gaps(observations),
        sources=sources,
    )


def run_macro_agent(
    agent: str,
    input_path,
    *,
    config_path=None,
    write_outputs: bool = True,
) -> MacroAgentReport:
    _configure_logging()
    source = Path(input_path).expanduser().resolve()
    config = load_macro_config(config_path)
    catalog_path = discover_catalog(source, agent)
    report = build_report(agent=agent, catalog_path=catalog_path, config=config)
    if write_outputs:
        root = data_root_for(source)
        out_dir = report_dir_for(root, agent)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / AGENT_REPORT_FILES[agent]
        out_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
        report.report_output_path = display_path(out_path)
        logger.info("macro_written agent=%s path=%s", agent, out_path)
    return report
