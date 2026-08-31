"""Specialist macro agents and MacroContextBrain. POS values are never recalculated."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agents.consumer_retail import run_consumer_retail
from backend.agents.energy_commodity import run_energy_commodity
from backend.agents.inflation_cost import run_inflation_cost
from backend.agents.macro_brain import run_macro_brain
from backend.agents.macro_common.calc import subtract
from backend.agents.macro_common.catalog import MacroLoadError
from backend.agents.macro_common.engine import run_macro_agent
from backend.agents.macro_common.language import assert_no_causal_language
from backend.agents.rates_fx import run_rates_fx
from backend.tests.macro_helpers import series, write_catalog
from backend.tests.storytelling_helpers import write_one_slide

DATA_ROOT = Path("backend/data")
FROZEN_PACK = DATA_ROOT / "macro_context" / "macro_context_v1.json"


def test_all_four_agents_load() -> None:
    inflation = run_inflation_cost(DATA_ROOT, write_outputs=False)
    consumer = run_consumer_retail(DATA_ROOT, write_outputs=False)
    rates = run_rates_fx(DATA_ROOT, write_outputs=False)
    energy = run_energy_commodity(DATA_ROOT, write_outputs=False)
    assert inflation.agent == "InflationCostAgent"
    assert consumer.agent == "ConsumerRetailAgent"
    assert rates.agent == "RatesFXAgent"
    assert energy.agent == "EnergyCommodityAgent"
    assert inflation.observations
    assert consumer.observations
    assert rates.observations
    assert energy.observations


def test_source_traceability() -> None:
    for runner in (run_inflation_cost, run_consumer_retail, run_rates_fx, run_energy_commodity):
        report = runner(DATA_ROOT, write_outputs=False)
        assert report.sources
        for item in report.observations:
            assert item.source
            assert item.source_url.startswith("http")
            host_ok = any(
                host in item.source_url
                for host in ("statssa.gov.za", "resbank.co.za", "ber.ac.za", "gov.za")
            )
            assert host_ok


def test_cci_signal_retained() -> None:
    report = run_consumer_retail(DATA_ROOT, write_outputs=False)
    cci = next(item for item in report.observations if item.metric == "FNB_BER_CCI")
    assert cci.value == pytest.approx(-19.0)
    assert cci.previous_value == pytest.approx(-7.0)
    assert cci.observation_date == "2026-06-30"
    assert cci.publication_date == "2026-06-23"
    pack = json.loads(FROZEN_PACK.read_text(encoding="utf-8"))
    assert pack["evidence"] == "FNB/BER CCI = -19"
    assert pack["evidence_as_of"] is None


def test_missing_values_are_not_zero(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        "InflationCostAgent",
        [
            series(
                "HEADLINE_CPI_YOY",
                [{"observation_date": "2026-07-31", "publication_date": "2026-08-19", "value": None}],
            )
        ],
        "inflation_cost.json",
    )
    report = run_macro_agent("InflationCostAgent", tmp_path, write_outputs=False)
    item = report.observations[0]
    assert item.value is None
    assert item.mom_change is None
    assert item.value != 0
    assert item.mom_change != 0
    assert any("missing" in gap.lower() or "null" in gap.lower() for gap in report.data_gaps) or item.value is None


def test_missing_previous_does_not_fabricate_mom(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        "InflationCostAgent",
        [
            series(
                "HEADLINE_CPI_YOY",
                [{"observation_date": "2026-07-31", "publication_date": "2026-08-19", "value": 4.3}],
            )
        ],
        "inflation_cost.json",
    )
    item = run_macro_agent("InflationCostAgent", tmp_path, write_outputs=False).observations[0]
    assert item.value == pytest.approx(4.3)
    assert item.previous_value is None
    assert item.mom_change is None


def test_historical_observations_drive_mom_and_yoy(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        "InflationCostAgent",
        [
            series(
                "HEADLINE_CPI_INDEX",
                [
                    {"observation_date": "2025-07-31", "publication_date": "2025-08-20", "value": 100.0},
                    {"observation_date": "2026-06-30", "publication_date": "2026-07-22", "value": 107.5},
                    {"observation_date": "2026-07-31", "publication_date": "2026-08-19", "value": 107.7},
                ],
                unit="index",
            )
        ],
        "inflation_cost.json",
    )
    item = run_macro_agent("InflationCostAgent", tmp_path, write_outputs=False).observations[0]
    assert item.previous_value == pytest.approx(107.5)
    assert item.year_ago_value == pytest.approx(100.0)
    assert item.mom_change == pytest.approx(0.2)
    assert item.yoy_change == pytest.approx(7.7)
    assert subtract(107.7, 107.5) == pytest.approx(0.2)
    assert subtract(107.7, 100.0) == pytest.approx(7.7)


def test_headline_cpi_mom_from_sourced_catalog() -> None:
    item = next(
        row
        for row in run_inflation_cost(DATA_ROOT, write_outputs=False).observations
        if row.metric == "HEADLINE_CPI_YOY"
    )
    assert item.value == pytest.approx(4.3)
    assert item.previous_value == pytest.approx(5.0)
    assert item.mom_change == pytest.approx(-0.7)
    assert item.yoy_change == pytest.approx(4.3)
    assert item.direction == "DOWN"
    assert item.signal_strength == "HIGH"
    assert item.fmcg_relevance == "HIGH"
    assert "PRICE" in item.commercial_levers


def test_direction_and_signal_strength(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        "RatesFXAgent",
        [
            series(
                "SARB_POLICY_RATE",
                [
                    {"observation_date": "2026-05-28", "publication_date": "2026-05-28", "value": 6.75},
                    {"observation_date": "2026-07-23", "publication_date": "2026-07-23", "value": 7.0},
                ],
                unit="percent",
                source="South African Reserve Bank",
                source_url="https://www.resbank.co.za/",
                commercial_levers=["PRICE"],
                fmcg_channels=["CONSUMER_AFFORDABILITY"],
            )
        ],
        "rates_fx.json",
    )
    item = run_macro_agent("RatesFXAgent", tmp_path, write_outputs=False).observations[0]
    assert item.direction == "UP"
    assert item.mom_change == pytest.approx(0.25)
    assert item.signal_strength == "MEDIUM"
    assert item.commercial_pressure == "TIGHTENING"


def test_date_alignment_and_future_leakage(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        "InflationCostAgent",
        [
            series(
                "HEADLINE_CPI_YOY",
                [{"observation_date": "2026-09-30", "publication_date": "2026-10-21", "value": 4.1}],
            )
        ],
        "inflation_cost.json",
    )
    item = run_macro_agent("InflationCostAgent", tmp_path, write_outputs=False).observations[0]
    assert item.alignment_status == "FUTURE_LEAKAGE"
    assert "after_pos_period_end" in item.alignment_method
    write_one_slide(tmp_path / "brain_reports" / "panel.brain.json")
    write_catalog(
        tmp_path,
        "ConsumerRetailAgent",
        [series("FNB_BER_CCI", [{"observation_date": "2026-06-30", "value": -19}])],
        "consumer_retail.json",
    )
    write_catalog(
        tmp_path,
        "RatesFXAgent",
        [series("SARB_POLICY_RATE", [{"observation_date": "2026-07-23", "value": 7.0}])],
        "rates_fx.json",
    )
    write_catalog(
        tmp_path,
        "EnergyCommodityAgent",
        [series("BRENT_REVIEW_AVERAGE_USD", [{"observation_date": "2026-08-03", "value": 82.37}])],
        "energy_commodity.json",
    )
    brain = run_macro_brain(tmp_path, write_outputs=False)
    leaked = [row for row in brain.alignments if row.metric == "HEADLINE_CPI_YOY"]
    assert leaked
    assert leaked[0].relation == "INSUFFICIENT_EVIDENCE"


def test_undated_observation_is_not_inferred(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        "ConsumerRetailAgent",
        [
            series(
                "FNB_BER_CCI",
                [{"observation_date": None, "publication_date": None, "value": -19.0}],
                unit="index_point",
                source="Bureau for Economic Research",
                source_url="https://www.ber.ac.za/Documents/Index/FNBBER-Consumer-Confidence-Index",
            )
        ],
        "consumer_retail.json",
    )
    item = run_macro_agent("ConsumerRetailAgent", tmp_path, write_outputs=False).observations[0]
    assert item.observation_date is None
    assert item.alignment_status == "INSUFFICIENT_DATES"


def test_fmcg_relevance_and_lever_mapping() -> None:
    energy = run_energy_commodity(DATA_ROOT, write_outputs=False)
    diesel = next(item for item in energy.observations if item.metric == "DIESEL_0_05_CHANGE_CPL")
    assert diesel.fmcg_relevance == "HIGH"
    assert "DISTRIBUTION" in diesel.commercial_levers
    assert "IMPORT_COST" in diesel.fmcg_channels
    rates = run_rates_fx(DATA_ROOT, write_outputs=False)
    fx = next(item for item in rates.observations if item.metric == "ZAR_USD_REVIEW_AVERAGE")
    assert "IMPORT_COST" in fx.fmcg_channels
    assert "PRICE" in fx.commercial_levers


def test_no_causal_language_on_real_reports() -> None:
    texts: list[str] = []
    for runner in (run_inflation_cost, run_consumer_retail, run_rates_fx, run_energy_commodity):
        report = runner(DATA_ROOT, write_outputs=False)
        texts.extend(report.commercial_implications)
        texts.extend(item.summary for item in report.signals)
    assert_no_causal_language(texts)
    blob = " ".join(texts).lower()
    assert "will increase" not in blob
    assert "causes" not in blob
    assert "caused" not in blob


def test_macro_brain_integration_does_not_rescore_pos() -> None:
    brain = run_macro_brain(DATA_ROOT, write_outputs=False)
    assert brain.agent == "MacroContextBrain"
    assert brain.causality_claim == "none"
    assert brain.verdict in {"SUPPORTS", "ADD_CONTEXT", "NEUTRAL", "CONTRADICTS", "INSUFFICIENT_EVIDENCE"}
    assert brain.pos_story.dominant_lever == "DISTRIBUTION"
    assert brain.pos_story.total_addressable_value_opportunity == pytest.approx(588562.67)
    assert brain.pos_story.total_addressable_volume_opportunity == pytest.approx(14521.165)
    assert brain.pos_story.n_actions == 3
    assert "CCI" not in (brain.pos_story.headline or "")
    cci = next(item for item in brain.alignments if item.metric == "FNB_BER_CCI")
    assert cci.relation == "SUPPORTS"
    action_note = " ".join(brain.fmcg_implications).lower()
    blob = " ".join([*brain.fmcg_implications, brain.overall_environment, *brain.limitations]).lower()
    assert "does not create a new commercial action" in action_note
    assert "not guaranteed incremental sales" in blob
    assert "causes" not in blob
    future = [item for item in brain.alignments if item.alignment_status == "FUTURE_LEAKAGE"]
    assert all(item.relation == "INSUFFICIENT_EVIDENCE" for item in future)


def test_malformed_catalog_fails(tmp_path: Path) -> None:
    path = tmp_path / "macro_observations" / "inflation_cost.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(MacroLoadError):
        run_macro_agent("InflationCostAgent", tmp_path, write_outputs=False)


def test_publication_lag_labelled() -> None:
    ppi = next(
        item
        for item in run_inflation_cost(DATA_ROOT, write_outputs=False).observations
        if item.metric == "PPI_FINAL_MANUFACTURING_YOY"
    )
    assert ppi.publication_date == "2026-08-27"
    assert ppi.observation_date == "2026-07-31"
    assert ppi.alignment_status == "ALIGNED_WITH_PUBLICATION_LAG"
    assert ppi.pos_period_end == "2026-08-16"
