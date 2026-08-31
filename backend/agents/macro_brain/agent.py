"""MacroContextBrain: supporting context only. Does not rescore Commercial Brain V1."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.agents.macro_common.catalog import (
    MacroLoadError,
    data_root_for,
    display_path,
    read_json_object,
)
from backend.agents.macro_common.engine import run_macro_agent
from backend.agents.macro_common.language import assert_no_causal_language
from backend.agents.macro_common.models import (
    BrainAlignment,
    BrainRelation,
    MacroAgentReport,
    MacroAgentStatus,
    MacroBrainReport,
    MacroConfig,
    MacroObservation,
    PosStoryCopy,
    load_macro_config,
)

logger = logging.getLogger("backend.agents.macro_brain")

SPECIALISTS = (
    "InflationCostAgent",
    "ConsumerRetailAgent",
    "RatesFXAgent",
    "EnergyCommodityAgent",
)

BRAIN_LIMITATIONS = [
    "MacroContextBrain consumes the four specialist macro agents only as supporting context.",
    "It does not recalculate POS opportunities or change opportunity values.",
    "It does not change Distribution, Price, Promotion, or Commercial Brain confidence.",
    "It does not create a new commercial action.",
    "It does not claim that macro conditions cause POS gaps.",
    "Future macro observations are not used to explain historical POS periods.",
    "Addressable POS opportunity remains not guaranteed incremental sales.",
    "Storytelling Engine V1 and its frozen macro pack are not modified.",
]


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _extract_one_slide(payload: dict) -> dict:
    if isinstance(payload.get("one_slide"), dict):
        return payload["one_slide"]
    if isinstance(payload.get("top_actions"), list):
        return payload
    raise MacroLoadError("JSON is not a Commercial Brain one-slide or *.brain.json report")


def discover_brain_slide(path: Path) -> tuple[dict, Path]:
    path = path.expanduser().resolve()
    if path.is_file():
        return _extract_one_slide(read_json_object(path, kind="Commercial Brain slide")), path
    named = [
        path / "commercial_brain_v1_one_slide.json",
        path / "brain_reports" / "commercial_brain_v1_one_slide.json",
    ]
    candidates = [item for item in named if item.is_file()]
    brain_dir = path / "brain_reports"
    if brain_dir.is_dir():
        candidates.extend(sorted(brain_dir.glob("*.brain.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    if not candidates:
        raise MacroLoadError(f"No Commercial Brain JSON under {path}")
    chosen = candidates[0]
    return _extract_one_slide(read_json_object(chosen, kind="Commercial Brain slide")), chosen


def copy_pos_story(slide: dict, source: Path) -> PosStoryCopy:
    actions = slide.get("top_actions") or []
    return PosStoryCopy(
        headline=None if slide.get("headline") is None else str(slide.get("headline")),
        dominant_lever=_dominant_lever(slide, actions),
        total_addressable_value_opportunity=_num(
            slide.get("total_addressable_value_opportunity", slide.get("total_estimated_value_opportunity"))
        ),
        total_addressable_volume_opportunity=_num(
            slide.get("total_addressable_volume_opportunity", slide.get("total_estimated_volume_opportunity"))
        ),
        n_actions=len(actions) if isinstance(actions, list) else None,
        source_brain_slide=display_path(source),
    )


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dominant_lever(slide: dict, actions: object) -> str | None:
    if slide.get("dominant_lever"):
        return str(slide["dominant_lever"])
    if not isinstance(actions, list) or not actions:
        return None
    levers = [str(item.get("lever") or "") for item in actions if isinstance(item, dict)]
    if not levers:
        return None
    return max(set(levers), key=levers.count)


def relate_observation(obs: MacroObservation, dominant_lever: str | None) -> BrainAlignment:
    lever = (dominant_lever or "").upper()
    if obs.alignment_status == "FUTURE_LEAKAGE":
        relation: BrainRelation = "INSUFFICIENT_EVIDENCE"
        reason = "Observation is after the POS period and is not used to explain POS."
    elif obs.alignment_status == "INSUFFICIENT_DATES" or obs.value is None:
        relation = "INSUFFICIENT_EVIDENCE"
        reason = "Observation is missing a sourced value or observation date."
    elif obs.fmcg_relevance == "NONE":
        relation = "NEUTRAL"
        reason = "Metric has no documented FMCG relevance."
    elif obs.metric == "FNB_BER_CCI" and obs.value is not None and obs.value < 0:
        relation = "SUPPORTS"
        reason = (
            "A negative CCI is consistent with value-conscious demand and with availability remaining important. "
            "It does not cause the POS gaps."
        )
    elif (
        obs.unit == "percent_yoy"
        and obs.value is not None
        and obs.value >= 10
        and "CONSUMER_AFFORDABILITY" in obs.fmcg_channels
    ):
        relation = "SUPPORTS"
        reason = (
            "The year-on-year print remains elevated for household budgets. That supports availability "
            "and targeted execution, without changing POS values."
        )
    elif "CONSUMER_AFFORDABILITY" in obs.fmcg_channels and obs.commercial_pressure == "TIGHTENING":
        relation = "SUPPORTS"
        reason = (
            "Tighter household affordability is consistent with a value-conscious shopper "
            "and with availability remaining important. It does not cause the POS gaps."
        )
    elif "DISTRIBUTION" in obs.commercial_levers and obs.commercial_pressure == "TIGHTENING":
        relation = "SUPPORTS"
        reason = (
            "Cost or confidence pressure raises the importance of being in-stock, "
            "without changing store-gap values."
        )
    elif lever == "DISTRIBUTION" and obs.commercial_pressure == "EASING" and "PRICE" in obs.commercial_levers:
        relation = "ADD_CONTEXT"
        reason = (
            "Softer cost inflation is relevant to PRICE later, not a reason to drop "
            "the named distribution actions."
        )
    elif obs.commercial_pressure == "EASING":
        relation = "ADD_CONTEXT"
        reason = "The print eases pressure but does not contradict the Commercial Brain ranking."
    elif obs.commercial_pressure in {"NEUTRAL", "INSUFFICIENT"}:
        relation = "NEUTRAL" if obs.commercial_pressure == "NEUTRAL" else "INSUFFICIENT_EVIDENCE"
        reason = "The sourced move is too incomplete or unchanged to support or contradict the POS ranking."
    else:
        relation = "ADD_CONTEXT"
        reason = "Macro print is commercially relevant context and is not used to rescore POS opportunities."
    return BrainAlignment(
        agent="",
        metric=obs.metric,
        relation=relation,
        reason=reason,
        alignment_status=obs.alignment_status,
        commercial_levers=list(obs.commercial_levers),
        fmcg_channels=list(obs.fmcg_channels),
    )


def overall_verdict(alignments: list[BrainAlignment]) -> BrainRelation:
    usable = [item for item in alignments if item.relation != "INSUFFICIENT_EVIDENCE"]
    if not usable:
        return "INSUFFICIENT_EVIDENCE"
    counts = {label: 0 for label in ("SUPPORTS", "CONTRADICTS", "ADD_CONTEXT", "NEUTRAL")}
    for item in usable:
        counts[item.relation] = counts.get(item.relation, 0) + 1
    if counts["CONTRADICTS"] > counts["SUPPORTS"]:
        return "CONTRADICTS"
    if counts["SUPPORTS"] > 0:
        return "SUPPORTS"
    if counts["ADD_CONTEXT"] > 0:
        return "ADD_CONTEXT"
    return "NEUTRAL"


def overall_environment(verdict: BrainRelation, observations: list[MacroObservation]) -> str:
    cci = next((item for item in observations if item.metric == "FNB_BER_CCI"), None)
    fuel = next((item for item in observations if item.metric == "FUEL_CPI_YOY"), None)
    headline = next((item for item in observations if item.metric == "HEADLINE_CPI_YOY"), None)
    bits = ["Households remain under pressure even where some inflation prints have eased."]
    if cci is not None and cci.value is not None:
        bits.append(f"FNB/BER CCI is {cci.value:.0f}.")
    if headline is not None and headline.value is not None:
        bits.append(f"Headline CPI is {headline.value}% year-on-year.")
    if fuel is not None and fuel.value is not None:
        bits.append(f"Fuel CPI is still {fuel.value}% year-on-year.")
    bits.append(f"MacroContextBrain verdict versus the POS ranking: {verdict}.")
    bits.append("This is supporting context, not a causal explanation of POS gaps.")
    return " ".join(bits)


def fmcg_implications(verdict: BrainRelation) -> list[str]:
    return [
        "DISTRIBUTION: value-conscious demand raises the cost of being out of stock on the named grains.",
        "PRICE: like-for-like tests remain relevant where coverage is already adequate; "
        "macro does not invent a price cut.",
        "PROMOTION: targeted tests remain secondary to availability where store gaps are the constraint.",
        "CONSUMER_AFFORDABILITY, MANUFACTURER_COST, RETAILER_PRESSURE and IMPORT_COST are context channels only.",
        f"Commercial Brain alignment: {verdict}. Macro does not create a new commercial action.",
    ]


def load_or_run_specialists(
    data_root: Path,
    *,
    config_path: Path | None,
    write_outputs: bool,
) -> list[MacroAgentReport]:
    reports: list[MacroAgentReport] = []
    for agent in SPECIALISTS:
        reports.append(
            run_macro_agent(agent, data_root, config_path=config_path, write_outputs=write_outputs)
        )
    return reports


def run_macro_brain(
    input_path: str | Path,
    *,
    config_path: str | Path | None = None,
    write_outputs: bool = True,
) -> MacroBrainReport:
    _configure_logging()
    source = Path(input_path).expanduser().resolve()
    root = data_root_for(source)
    config: MacroConfig = load_macro_config(None if config_path is None else Path(config_path))
    slide, brain_file = discover_brain_slide(source if source.is_dir() else root)
    pos = copy_pos_story(slide, brain_file)
    cfg = None if config_path is None else Path(config_path)
    specialists = load_or_run_specialists(root, config_path=cfg, write_outputs=write_outputs)
    observations: list[MacroObservation] = []
    alignments: list[BrainAlignment] = []
    signals = []
    sources: list[str] = []
    gaps: list[str] = []
    implications: list[str] = []
    report_paths: list[str] = []
    for report in specialists:
        observations.extend(report.observations)
        signals.extend(report.signals)
        sources.extend(report.sources)
        gaps.extend(report.data_gaps)
        implications.extend(report.commercial_implications)
        if report.report_output_path:
            report_paths.append(report.report_output_path)
        for obs in report.observations:
            item = relate_observation(obs, pos.dominant_lever)
            item.agent = report.agent
            alignments.append(item)
    verdict = overall_verdict(alignments)
    environment = overall_environment(verdict, observations)
    notes = [*BRAIN_LIMITATIONS, *config.limitations]
    fmcg = fmcg_implications(verdict)
    assert_no_causal_language([environment, *implications, *fmcg, *notes], config)
    status = MacroAgentStatus.READY_WITH_WARNINGS if gaps else MacroAgentStatus.READY
    if not observations:
        status = MacroAgentStatus.NOT_READY
    report = MacroBrainReport(
        status=status,
        verdict=verdict,
        overall_environment=environment,
        pos_story=pos,
        pos_period_start=config.pos_period_start,
        pos_period_end=config.pos_period_end,
        alignments=alignments,
        specialist_reports=report_paths,
        observations=observations,
        signals=signals,
        commercial_implications=implications,
        fmcg_implications=fmcg,
        sources=sorted(set(sources)),
        data_gaps=gaps,
        limitations=notes,
    )
    if write_outputs:
        out_dir = root / "macro_brain_reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "macro_context_brain_v1.json"
        out_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
        report.report_output_path = display_path(out_path)
        logger.info("macro_brain_written path=%s verdict=%s", out_path, verdict)
    return report
