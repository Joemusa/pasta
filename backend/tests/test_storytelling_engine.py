"""Storytelling Engine V1 tests. Commercial Brain values must be copied, not recalculated."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.storytelling import STORYTELLING_VERSION, StorytellingLoadError, run_storytelling
from backend.agents.storytelling.models import METHODOLOGY_NOTE
from backend.agents.storytelling.narrative import build_headline, build_story, retailer_insight
from backend.tests.storytelling_helpers import brain_action, brain_one_slide, write_one_slide


def test_refuses_raw_and_commercial_csv(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "upload.csv"
    raw.parent.mkdir(parents=True)
    raw.write_text("x\n", encoding="utf-8")
    with pytest.raises(StorytellingLoadError, match="raw"):
        run_storytelling(raw)
    commercial = tmp_path / "panel.commercial.csv"
    commercial.write_text("x\n", encoding="utf-8")
    with pytest.raises(StorytellingLoadError, match="Brain JSON"):
        run_storytelling(commercial)


def test_exactly_one_headline_and_three_actions(tmp_path: Path) -> None:
    path = write_one_slide(tmp_path / "commercial_brain_v1_one_slide.json")
    report = run_storytelling(path)
    story = report.one_slide
    assert report.version == STORYTELLING_VERSION
    assert story.headline
    assert "\n" not in story.headline
    assert story.headline.count(".") <= 1
    assert len(story.actions) == 3
    assert [item.rank for item in story.actions] == [1, 2, 3]
    assert (path.parent / "storytelling_reports" / "storytelling_v1_one_slide.json").exists()


def test_headline_supported_by_data_and_no_forced_diversity() -> None:
    slide = brain_one_slide()
    story = build_story(slide)
    assert all(item.lever == "DISTRIBUTION" for item in story.actions)
    assert "Distribution" in story.headline
    assert "Price" not in story.headline
    assert "Promotion" not in story.headline
    assert story.dominant_lever == "DISTRIBUTION"
    assert "Shoprite" in story.headline
    mixed = brain_one_slide(
        actions=[
            brain_action(rank=1, lever="PRICE", retailer="Clicks", store_gap=0.0),
            brain_action(rank=2, lever="PRICE", retailer="Clicks", product="Vim 500g", store_gap=0.0),
            brain_action(rank=3, lever="PRICE", retailer="Spar", product="Domestos 750ml", store_gap=0.0),
        ]
    )
    price_story = build_story(mixed)
    assert price_story.dominant_lever == "PRICE"
    assert all(item.lever == "PRICE" for item in price_story.actions)
    assert "Distribution" not in price_story.headline


def test_retailer_insight_accuracy() -> None:
    slide = brain_one_slide()
    story = build_story(slide)
    assert story.retailer_insight == "SHOPRITE appears in 2 of the 3 priority actions"
    unique = brain_one_slide(
        actions=[
            brain_action(rank=1, retailer="Shoprite"),
            brain_action(rank=2, retailer="Checkers", region="Gauteng"),
            brain_action(rank=3, retailer="Makro Online", region="Gauteng"),
        ]
    )
    assert retailer_insight(unique["top_actions"]) == ""  # type: ignore[arg-type]
    assert build_story(unique).retailer_insight == ""


def test_values_volumes_and_confidence_preserved() -> None:
    slide = brain_one_slide()
    story = build_story(slide)
    source = slide["top_actions"]
    assert story.hero_metric.value == pytest.approx(588562.67)
    assert story.hero_volume.value == pytest.approx(14521.165)
    assert story.hero_metric.label == "Addressable value"
    assert story.hero_volume.label == "Addressable volume"
    for card, raw in zip(story.actions, source, strict=True):
        assert card.addressable_value == pytest.approx(float(raw["addressable_value"]))  # type: ignore[arg-type]
        assert card.addressable_volume == pytest.approx(float(raw["addressable_volume"]))  # type: ignore[arg-type]
        assert card.confidence == raw["confidence"]
        assert card.product == raw["product"]
        assert card.retailer == raw["retailer"]


def test_store_gap_and_action_language() -> None:
    story = build_story(brain_one_slide())
    first = story.actions[0]
    assert first.store_gap == pytest.approx(24.0)
    assert first.headline == "Close the 24-store distribution gap"
    assert "Close the 24-store gap toward the like-for-like benchmark at Shoprite" in first.recommended_action
    assert "Improve distribution" not in first.recommended_action
    assert "Improve sales" not in first.recommended_action


def test_no_causal_or_guaranteed_incremental_claims() -> None:
    story = build_story(brain_one_slide())
    blob = " ".join(
        [
            story.headline,
            story.subheadline,
            story.key_insight,
            story.commercial_implication,
            story.methodology_note,
            " ".join(item.headline + " " + item.recommended_action for item in story.actions),
        ]
    ).lower()
    assert "not guaranteed incremental sales" in story.methodology_note.lower()
    assert "analysis" not in story.headline.lower()
    assert "performance" not in story.headline.lower()
    assert "will increase" not in blob
    assert "causes" not in blob
    assert "addressable value" in blob or "addressable" in story.hero_metric.label.lower()
    assert "addressable" in story.subheadline.lower()
    assert story.methodology_note == METHODOLOGY_NOTE
    assert "4 POS weeks" in story.data_coverage
    assert "3 overlapping weeks" in story.data_coverage
    assert story.commercial_implication
    assert "distribution expansion" in story.commercial_implication.lower()
    assert story.macro_context.role == "absent"
    assert story.macro_context.included is False


def test_headline_builder_uses_repeating_retailer() -> None:
    actions = brain_one_slide()["top_actions"]
    headline = build_headline(actions, "DISTRIBUTION")  # type: ignore[arg-type]
    assert "Shoprite" in headline
    assert "clearest" in headline.lower()


def test_brain_report_wrapper(tmp_path: Path) -> None:
    payload = {"one_slide": brain_one_slide(), "limitations": ["extra"]}
    path = tmp_path / "panel.brain.json"
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    report = run_storytelling(path, write_outputs=False)
    assert len(report.one_slide.actions) == 3
    assert report.causality_claim == "none"


def test_real_brain_report_if_present() -> None:
    target = Path("backend/data")
    brain_dir = target / "brain_reports"
    files = list(brain_dir.glob("*.brain.json")) if brain_dir.exists() else []
    if not files:
        pytest.skip("Commercial Brain report is not in this checkout")
    report = run_storytelling(target, write_outputs=False)
    story = report.one_slide
    assert story.headline
    assert len(story.actions) == 3
    assert story.methodology_note == METHODOLOGY_NOTE
    assert all(item.confidence in {"HIGH", "MEDIUM", "LOW"} for item in story.actions)
    assert story.hero_metric.value > 0
    assert story.hero_volume.value > 0
