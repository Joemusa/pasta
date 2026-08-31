"""Frozen macro context is supporting background only. It does not rescore the POS story."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agents.storytelling import StorytellingLoadError, run_storytelling
from backend.agents.storytelling.macro import attach_macro_context, parse_macro_pack
from backend.agents.storytelling.models import MACRO_CAUSALITY_DISCLAIMER
from backend.agents.storytelling.narrative import assert_no_unsupported_claims, build_story
from backend.tests.storytelling_helpers import (
    brain_action,
    brain_one_slide,
    macro_pack,
    write_macro_pack,
    write_one_slide,
)


def test_macro_is_optional(tmp_path: Path) -> None:
    path = write_one_slide(tmp_path / "commercial_brain_v1_one_slide.json")
    report = run_storytelling(path, write_outputs=False)
    assert report.source_macro_pack is None
    assert report.one_slide.macro_context.role == "absent"
    assert report.one_slide.macro_context.included is False
    assert report.one_slide.macro_context.supporting_line == ""


def test_supporting_macro_does_not_replace_pos_headline(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_one_slide(data_root / "commercial_brain_v1_one_slide.json")
    write_macro_pack(data_root)
    pos = build_story(brain_one_slide())
    with_macro = run_storytelling(data_root, write_outputs=False)
    story = with_macro.one_slide
    assert pos.macro_context.role == "absent"
    assert story.headline == pos.headline
    assert "Distribution" in story.headline
    assert "Shoprite" in story.headline
    assert "CCI" not in story.headline
    assert "Consumer pressure" not in story.headline
    assert story.subheadline == pos.subheadline
    assert story.key_insight == pos.key_insight
    assert story.commercial_implication == pos.commercial_implication
    assert "distribution expansion" in story.commercial_implication.lower()
    assert story.macro_context.included is True
    assert story.macro_context.role == "supporting_context"
    assert story.macro_context.supports_pos_story is True
    assert story.macro_context.signal == "Consumer pressure increasing"
    assert story.macro_context.evidence == "FNB/BER CCI = -19"
    assert story.macro_context.direction == "NEGATIVE"
    assert story.macro_context.relevance == "HIGH"
    assert story.macro_context.confidence == "HIGH"
    assert story.macro_context.sources == ["SARB", "BER", "Stats SA"]
    assert story.macro_context.evidence_as_of is None
    assert story.macro_context.supporting_line.startswith("Supporting context:")
    assert "FNB/BER CCI = -19" in story.macro_context.supporting_line
    assert story.macro_context.causality_disclaimer == MACRO_CAUSALITY_DISCLAIMER
    assert with_macro.source_macro_pack is not None


def test_pos_values_and_confidence_unchanged_by_macro(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_one_slide(data_root / "commercial_brain_v1_one_slide.json")
    write_macro_pack(data_root)
    story = run_storytelling(data_root).one_slide
    source = brain_one_slide()["top_actions"]
    assert story.hero_metric.value == pytest.approx(588562.67)
    assert story.hero_volume.value == pytest.approx(14521.165)
    assert all(item.lever == "DISTRIBUTION" for item in story.actions)
    assert [item.confidence for item in story.actions] == ["HIGH", "HIGH", "HIGH"]
    for card, raw in zip(story.actions, source, strict=True):
        assert card.addressable_value == pytest.approx(float(raw["addressable_value"]))  # type: ignore[arg-type]
        assert card.addressable_volume == pytest.approx(float(raw["addressable_volume"]))  # type: ignore[arg-type]
        assert card.confidence == raw["confidence"]
        assert card.product == raw["product"]
        assert card.retailer == raw["retailer"]


def test_macro_high_confidence_does_not_upgrade_pos(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_one_slide(
        data_root / "commercial_brain_v1_one_slide.json",
        brain_one_slide(
            actions=[
                brain_action(rank=1, confidence="MEDIUM"),
                brain_action(rank=2, product="Sunlight Pine Gel 1l", confidence="LOW", store_gap=13.0),
                brain_action(
                    rank=3,
                    product="Handy Andy Eucalyptus 5l",
                    retailer="Makro Online",
                    confidence="MEDIUM",
                    store_gap=3.0,
                ),
            ]
        ),
    )
    write_macro_pack(data_root, macro_pack(confidence="HIGH"))
    story = run_storytelling(data_root, write_outputs=False).one_slide
    assert story.macro_context.confidence == "HIGH"
    assert [item.confidence for item in story.actions] == ["MEDIUM", "LOW", "MEDIUM"]


def test_macro_does_not_invent_price_or_promotion_actions(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_one_slide(data_root / "commercial_brain_v1_one_slide.json")
    write_macro_pack(data_root)
    story = run_storytelling(data_root, write_outputs=False).one_slide
    assert {item.lever for item in story.actions} == {"DISTRIBUTION"}
    assert "Price" not in story.headline
    assert "Promotion" not in story.headline
    assert len(story.actions) == 3


def test_unsupported_macro_is_recorded_not_shown(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_one_slide(data_root / "commercial_brain_v1_one_slide.json")
    write_macro_pack(data_root, macro_pack(supports_pos_story=False))
    story = run_storytelling(data_root, write_outputs=False).one_slide
    assert story.macro_context.included is False
    assert story.macro_context.role == "excluded"
    assert story.macro_context.supporting_line == ""
    assert story.macro_context.supports_pos_story is False
    assert "CCI" not in story.headline
    assert story.macro_context.exclusion_reason is not None


def test_malformed_macro_pack_fails(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_one_slide(data_root / "commercial_brain_v1_one_slide.json")
    path = write_macro_pack(data_root, {"signal": "only"})
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(StorytellingLoadError, match="frozen macro"):
        run_storytelling(data_root, write_outputs=False)


def test_macro_missing_fields_fail(tmp_path: Path) -> None:
    path = tmp_path / "macro_context_v1.json"
    path.write_text(json.dumps({"signal": "x"}), encoding="utf-8")
    with pytest.raises(StorytellingLoadError, match="missing fields"):
        parse_macro_pack({"signal": "x"}, path)


def test_macro_does_not_claim_causality() -> None:
    story = build_story(brain_one_slide())
    block = parse_macro_pack(macro_pack(), Path("backend/data/macro_context/macro_context_v1.json"))
    attached = attach_macro_context(story, block)
    assert_no_unsupported_claims(attached)
    blob = " ".join(
        [
            attached.headline,
            attached.subheadline,
            attached.key_insight,
            attached.commercial_implication,
            attached.macro_context.supporting_line,
            attached.macro_context.causality_disclaimer,
            attached.macro_context.commercial_implication or "",
        ]
    ).lower()
    assert "will increase" not in blob
    assert "causes" not in blob
    assert "caused" not in blob
    assert "does not cause" in attached.macro_context.causality_disclaimer.lower()
    assert "not guaranteed incremental sales" in attached.methodology_note.lower()


def test_real_macro_pack_if_present() -> None:
    target = Path("backend/data")
    pack = target / "macro_context" / "macro_context_v1.json"
    if not pack.exists():
        pytest.skip("Frozen macro context pack is not in this checkout")
    report = run_storytelling(target, write_outputs=False)
    story = report.one_slide
    assert story.headline
    assert "Distribution" in story.headline
    assert "CCI" not in story.headline
    assert story.macro_context.included is True
    assert story.macro_context.evidence == "FNB/BER CCI = -19"
    assert story.hero_metric.value == pytest.approx(588562.67)
    assert all(item.confidence == "HIGH" for item in story.actions)
    assert all(item.lever == "DISTRIBUTION" for item in story.actions)
    assert story.macro_context.evidence_as_of is None
