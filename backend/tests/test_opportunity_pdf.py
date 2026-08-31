"""Opportunity Pulse PDF tests. Ranking and values are copied from Commercial Brain, not recalculated."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pypdf import PdfReader

from backend.reports.assemble import assemble
from backend.reports.loader import ReportInputs, social_block
from backend.reports.render import render_executive_pdf, render_full_pdf

SOURCE_DIR = Path("backend/reports")
FORBIDDEN_HARDCODES = (
    "4534.32",
    "2709.84",
    "2653.32",
    "588562",
    "Sunlight Pine Gel 500ml",
    "Handy Andy All Purpose Cleaner Eucalyptus",
)
GUARANTEED = re.compile(r"(?<!not )guaranteed incremental sales", re.IGNORECASE)


def _pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", raw)


def _write_brain(path: Path) -> Path:
    payload = {
        "status": "READY WITH WARNINGS",
        "manufacturer": "Unilever",
        "current_period": "2026-01-04",
        "causality_claim": "none",
        "headline": "Distribution is currently the clearest growth lever in the priority opportunities",
        "storytelling": {
            "core_message": "Distribution is currently the clearest growth lever in the priority opportunities",
            "quantified_opportunity": "Addressable value is directional, not guaranteed incremental sales.",
            "next_step": "Start with Action 1 as a test, not booked revenue.",
        },
        "top_actions": [
            {
                "rank": 1,
                "action_number": 1,
                "lever": "DISTRIBUTION",
                "headline": "Expand distribution of Fixture SKU A in Region One",
                "why": (
                    "Coverage sits below the benchmark. "
                    "This is addressable opportunity, not guaranteed incremental sales."
                ),
                "product": "Fixture SKU A",
                "brand": "FixtureBrand",
                "retailer": "FixtureMart",
                "region": "Region One",
                "estimated_value": 111.0,
                "estimated_volume": 11.0,
                "addressable_value": 111.0,
                "addressable_volume": 11.0,
                "current_sales": 50.0,
                "confidence": "LOW",
                "recommended_action": "Brief a listing test for Fixture SKU A.",
                "evidence": ["Double-counting risk: NONE."],
                "priority_score": 0.9,
            },
            {
                "rank": 2,
                "action_number": 2,
                "lever": "PRICE",
                "headline": "Test price position of Fixture SKU B at FixtureMart in Region Two",
                "why": "Price signal is directional, not guaranteed incremental sales.",
                "product": "Fixture SKU B",
                "brand": "FixtureBrand",
                "retailer": "FixtureMart",
                "region": "Region Two",
                "estimated_value": 222.0,
                "estimated_volume": 22.0,
                "addressable_value": 222.0,
                "addressable_volume": 22.0,
                "current_sales": None,
                "confidence": "MEDIUM",
                "recommended_action": "Run a like-for-like price test.",
                "evidence": ["Double-counting risk: MEDIUM."],
                "priority_score": 0.8,
            },
            {
                "rank": 3,
                "action_number": 3,
                "lever": "PROMOTION",
                "headline": "Target promotion of Fixture SKU C at OtherCo in Region One",
                "why": "Promotion response is directional, not guaranteed incremental sales.",
                "product": "Fixture SKU C",
                "brand": "OtherBrand",
                "retailer": "OtherCo",
                "region": "Region One",
                "estimated_value": 333.0,
                "estimated_volume": 33.0,
                "addressable_value": 333.0,
                "addressable_volume": 33.0,
                "current_sales": 90.0,
                "confidence": "HIGH",
                "recommended_action": "Test promotion where distribution is adequate.",
                "evidence": ["Double-counting risk: LOW."],
                "priority_score": 0.7,
            },
        ],
        "opportunities": [
            {
                "opportunity_id": "fix-1",
                "product": "Fixture SKU A",
                "brand": "FixtureBrand",
                "retailer": "FixtureMart",
                "region": "Region One",
                "dominant_lever": "DISTRIBUTION",
                "double_counting_risk": "NONE",
                "addressable_value_opportunity": 111.0,
                "addressable_volume_opportunity": 11.0,
                "current_sales": 50.0,
                "sales_per_store": 10.0,
                "volume_per_store": 2.0,
                "distribution_stores": 5.0,
                "distribution_gap": 4.0,
                "priority_score": 0.9,
                "confidence": "LOW",
                "recommended_action": "Brief a listing test for Fixture SKU A.",
                "evidence": ["Double-counting risk: NONE."],
                "limitations": ["Short POS history."],
            },
            {
                "opportunity_id": "fix-2",
                "product": "Fixture SKU B",
                "brand": "FixtureBrand",
                "retailer": "FixtureMart",
                "region": "Region Two",
                "dominant_lever": "PRICE",
                "double_counting_risk": "MEDIUM",
                "addressable_value_opportunity": 222.0,
                "addressable_volume_opportunity": 22.0,
                "current_sales": None,
                "sales_per_store": None,
                "volume_per_store": None,
                "distribution_stores": None,
                "distribution_gap": None,
                "priority_score": 0.8,
                "confidence": "MEDIUM",
                "recommended_action": "Run a like-for-like price test.",
                "evidence": [],
                "limitations": [],
            },
            {
                "opportunity_id": "fix-3",
                "product": "Fixture SKU C",
                "brand": "OtherBrand",
                "retailer": "OtherCo",
                "region": "Region One",
                "dominant_lever": "PROMOTION",
                "double_counting_risk": "LOW",
                "addressable_value_opportunity": 333.0,
                "addressable_volume_opportunity": 33.0,
                "current_sales": 90.0,
                "confidence": "HIGH",
                "recommended_action": "Test promotion where distribution is adequate.",
                "evidence": [],
                "limitations": [],
            },
        ],
        "limitations": [
            "4 POS weeks currently available.",
            "3 overlapping price/promotion weeks.",
            "Opportunity estimates are directional addressable values, not guaranteed incremental sales.",
        ],
        "methodology": "Copied from frozen specialists. Not guaranteed incremental sales.",
        "source_distribution_report": None,
        "source_price_report": None,
        "source_promotion_report": None,
        "source_integrated_file": None,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fixture_inputs(tmp_path: Path, *, include_macro: bool = True, include_social: bool = False) -> ReportInputs:
    data = tmp_path / "data"
    (data / "brain_reports").mkdir(parents=True, exist_ok=True)
    brain_path = _write_brain(data / "brain_reports" / "fixture.brain.json")
    story = {
        "headline": "Fixture distribution is the clearest near-term growth opportunity",
        "subheadline": "Three ranked actions represent addressable opportunity, not guaranteed incremental sales.",
        "commercial_implication": "Prioritize the named grains in rank order.",
        "dominant_lever": "DISTRIBUTION",
        "key_insight": "FixtureMart appears in the priority set.",
        "actions": [
            {
                "rank": 1,
                "lever": "DISTRIBUTION",
                "headline": "Close the 4-store distribution gap",
                "product": "Fixture SKU A",
                "brand": "FixtureBrand",
                "retailer": "FixtureMart",
                "region": "Region One",
                "addressable_value": 111.0,
                "addressable_volume": 11.0,
                "confidence": "LOW",
                "store_gap": 4.0,
                "recommended_action": "Brief a listing test for Fixture SKU A.",
            }
        ],
        "methodology_note": "Based on current POS data. Addressable opportunity is not guaranteed incremental sales.",
        "data_coverage": "4 POS weeks. Price/promotion: 3 overlapping weeks.",
        "limitations": ["Storytelling Engine V1 consumes Commercial Brain one-slide output only."],
        "macro_context": {
            "included": include_macro,
            "role": "supporting_context",
            "signal": "Consumer pressure increasing",
            "evidence": "FNB/BER CCI = -19",
            "confidence": "HIGH",
            "causality_disclaimer": (
                "Macro context is supporting background only. It does not cause or recalculate POS opportunities."
            ),
        }
        if include_macro
        else {"included": False, "role": "absent"},
    }
    (data / "storytelling_reports").mkdir(exist_ok=True)
    story_path = data / "storytelling_reports" / "storytelling_v1_one_slide.json"
    story_path.write_text(json.dumps(story), encoding="utf-8")
    if include_social:
        (data / "social_live_validation").mkdir(exist_ok=True)
        (data / "social_live_validation" / "gdelt_smoke_summary.json").write_text(
            json.dumps(
                {
                    "live_data_status": "LIVE — GDELT",
                    "records_successfully_normalised": 2,
                    "records_successfully_analysed": 2,
                    "observation_start": "2026-01-01T00:00:00Z",
                    "observation_end": "2026-01-31T00:00:00Z",
                    "top_brands_detected": ["Sunlight"],
                    "sentiment": {"label": "NEUTRAL"},
                }
            ),
            encoding="utf-8",
        )
    social = social_block(data)
    brain = json.loads(brain_path.read_text(encoding="utf-8"))
    return ReportInputs(
        root=data,
        brain_path=brain_path,
        brain=brain,
        storytelling_path=story_path,
        storytelling=story,
        distribution_path=None,
        distribution_index={},
        macro_path=None,
        macro=None,
        social=social,
        sources={"brain": str(brain_path), "storytelling": str(story_path)},
    )


def test_source_has_no_hardcoded_opportunity_values() -> None:
    blob = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE_DIR.glob("*.py"))
    for token in FORBIDDEN_HARDCODES:
        assert token not in blob


def test_top_three_copied_from_brain_not_independently_ranked(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    report = assemble(inputs)
    actions = inputs.brain["top_actions"]
    assert [item["rank"] for item in report["opportunities"]] == [1, 2, 3]
    assert [item["product"] for item in report["opportunities"]] == [row["product"] for row in actions]
    assert [item["addressable_value"] for item in report["opportunities"]] == [
        row["addressable_value"] for row in actions
    ]
    assert [item["confidence"] for item in report["opportunities"]] == [row["confidence"] for row in actions]
    assert report["opportunities"][1]["confidence"] == "MEDIUM"
    assert report["top3_sum"]["addressable_value"] == pytest.approx(111.0 + 222.0 + 333.0)
    assert report["top3_sum"]["label"] == "Addressable opportunity estimate"


def test_macro_does_not_change_ranking(tmp_path: Path) -> None:
    with_macro = assemble(_fixture_inputs(tmp_path, include_macro=True))
    without = assemble(_fixture_inputs(tmp_path, include_macro=False))
    assert [item["product"] for item in with_macro["opportunities"]] == [
        item["product"] for item in without["opportunities"]
    ]
    assert with_macro["opportunities"][0]["addressable_value"] == without["opportunities"][0]["addressable_value"]
    assert with_macro["macro"]["role"] == "supporting_context"


def test_missing_values_stay_missing(tmp_path: Path) -> None:
    report = assemble(_fixture_inputs(tmp_path))
    price = report["opportunities"][1]
    assert price["current_sales"]["available"] is False
    assert price["current_sales"]["display"] == "Not available"
    assert price["store_gap"]["available"] is False
    assert price["benchmark_stores"]["available"] is False
    assert price["current_sales"]["value"] is None


def test_social_not_fabricated_when_absent(tmp_path: Path) -> None:
    report = assemble(_fixture_inputs(tmp_path, include_social=False))
    assert report["social"]["connected"] is False
    assert report["social"]["display"] == "Social intelligence: not connected"
    assert report["social"]["validated_observations"] == []


def test_social_live_observations_keep_period(tmp_path: Path) -> None:
    report = assemble(_fixture_inputs(tmp_path, include_social=True))
    assert report["social"]["connected"] is True
    assert report["social"]["observation_start"] == "2026-01-01T00:00:00Z"
    assert report["social"]["validated_observations"]


def test_storytelling_headline_is_used(tmp_path: Path) -> None:
    report = assemble(_fixture_inputs(tmp_path))
    assert report["story"]["headline"] == "Fixture distribution is the clearest near-term growth opportunity"
    assert report["story"]["source"] == "Storytelling Engine V1"


def test_pdf_matches_json_and_renders(tmp_path: Path) -> None:
    report = assemble(_fixture_inputs(tmp_path))
    executive = render_executive_pdf(report, tmp_path / "exec.pdf")
    full = render_full_pdf(report, tmp_path / "full.pdf")
    assert executive.is_file() and executive.stat().st_size > 1000
    assert full.is_file() and full.stat().st_size > 1000
    exec_reader = PdfReader(str(executive))
    full_reader = PdfReader(str(full))
    assert len(exec_reader.pages) == 1
    assert len(full_reader.pages) == 5
    exec_text = _pdf_text(executive)
    full_text = _pdf_text(full)
    assert "COMMERCIAL OPPORTUNITY PULSE" in exec_text
    assert "Addressable opportunity estimate" in exec_text
    assert "Fixture SKU A" in exec_text
    assert "FixtureMart" in exec_text
    assert "LOW" in exec_text
    assert "Fixture distribution" in exec_text
    assert GUARANTEED.search(exec_text) is None
    assert "not guaranteed incremental sales" in exec_text.lower()
    assert "macro context" in exec_text.lower()
    assert "Social intelligence: not connected" in exec_text
    assert "Fixture SKU A" in full_text
    assert "Fixture SKU B" in full_text
    assert "Fixture SKU C" in full_text
    assert "Why this matters" in full_text
    assert "Recommended action" in full_text
    assert "Double-counting" in full_text


def test_live_top3_equals_persisted_brain() -> None:
    from backend.reports.loader import load_inputs

    report = assemble(load_inputs("backend/data"))
    brain = json.loads(Path(report["sources"]["brain"]).read_text(encoding="utf-8"))
    actions = brain["top_actions"][:3]
    assert [item["product"] for item in report["opportunities"]] == [row["product"] for row in actions]
    assert [item["retailer"] for item in report["opportunities"]] == [row["retailer"] for row in actions]
    assert [item["region"] for item in report["opportunities"]] == [row["region"] for row in actions]
    assert [item["addressable_value"] for item in report["opportunities"]] == [
        row["addressable_value"] for row in actions
    ]
    assert [item["confidence"] for item in report["opportunities"]] == [row["confidence"] for row in actions]
    assert report["top3_sum"]["addressable_value"] == pytest.approx(sum(row["addressable_value"] for row in actions))
    story_path = Path("backend/data/storytelling_reports/storytelling_v1_one_slide.json")
    story = json.loads(story_path.read_text(encoding="utf-8"))
    assert report["story"]["headline"] == story["headline"]
    assert report["story"]["commercial_implication"] == story["commercial_implication"]


def test_live_pdfs_match_json(tmp_path: Path) -> None:
    from backend.reports.loader import load_inputs

    report = assemble(load_inputs("backend/data"))
    executive = render_executive_pdf(report, tmp_path / "live_exec.pdf")
    full = render_full_pdf(report, tmp_path / "live_full.pdf")
    exec_text = _pdf_text(executive)
    full_text = _pdf_text(full)
    assert len(PdfReader(str(executive)).pages) == 1
    assert len(PdfReader(str(full)).pages) == 5
    for item in report["opportunities"]:
        assert item["product"] in exec_text
        assert item["product"] in full_text
        assert item["confidence"] in exec_text
    assert "Distribution" in exec_text
    assert GUARANTEED.search(exec_text) is None
    assert "not guaranteed incremental sales" in exec_text.lower()
    if report["social"]["connected"]:
        assert "GDELT" in exec_text or "Social intelligence" in exec_text
    else:
        assert "Social intelligence: not connected" in exec_text
    assert "macro context" in exec_text.lower()
    assert "Consumer pressure" in exec_text
