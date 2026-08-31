"""Cole Nussbaumer Knaflic-style one-slide narrative. Values are copied, not recalculated."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from backend.agents.storytelling.models import (
    DEFAULT_DATA_COVERAGE,
    METHODOLOGY_NOTE,
    V1_LIMITATIONS,
    HeroMetric,
    OneSlideStory,
    StoryAction,
    absent_macro_context,
)

_GAP_EVIDENCE = re.compile(r"store gap\s+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_GAP_HYPHEN = re.compile(r"([0-9]+(?:\.[0-9]+)?)-store gap", re.IGNORECASE)
_CAUSAL_FORBIDDEN = (
    "will increase",
    "causes",
    "caused",
    "guaranteed incremental sales",
    "booked revenue",
)


def _num(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return number


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def addressable_value(action: dict[str, Any]) -> float:
    for key in ("addressable_value", "addressable_value_opportunity", "estimated_value"):
        if action.get(key) is not None:
            return _num(action.get(key))
    return 0.0


def addressable_volume(action: dict[str, Any]) -> float:
    for key in ("addressable_volume", "addressable_volume_opportunity", "estimated_volume"):
        if action.get(key) is not None:
            return _num(action.get(key))
    return 0.0


def parse_store_gap(action: dict[str, Any]) -> float:
    if action.get("store_gap") is not None and action.get("store_gap") != "":
        return _num(action.get("store_gap"))
    blob = " ".join(
        [
            _text(action.get("why")),
            _text(action.get("recommended_action")),
            " ".join(str(item) for item in (action.get("evidence") or [])),
        ]
    )
    match = _GAP_EVIDENCE.search(blob) or _GAP_HYPHEN.search(blob)
    if match:
        return _num(match.group(1))
    return 0.0


def _rand_compact(value: float) -> str:
    if value >= 100_000:
        return f"R{value / 1000:,.0f}k"
    if value >= 1000:
        return f"R{value / 1000:.1f}k"
    return f"R{value:,.0f}"


def dominant_lever(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return "INSUFFICIENT EVIDENCE"
    counts: Counter[str] = Counter(_text(item.get("lever")) or "INSUFFICIENT EVIDENCE" for item in actions)
    value_by_lever: dict[str, float] = {}
    for item in actions:
        lever = _text(item.get("lever")) or "INSUFFICIENT EVIDENCE"
        value_by_lever[lever] = value_by_lever.get(lever, 0.0) + addressable_value(item)
    return max(counts.items(), key=lambda pair: (pair[1], value_by_lever.get(pair[0], 0.0), pair[0]))[0]


def repeating_retailer(actions: list[dict[str, Any]]) -> tuple[str, int] | None:
    counts: Counter[str] = Counter(_text(item.get("retailer")) for item in actions if _text(item.get("retailer")))
    if not counts:
        return None
    name, n = counts.most_common(1)[0]
    if n >= 2:
        return name, n
    return None


def retailer_insight(actions: list[dict[str, Any]]) -> str:
    found = repeating_retailer(actions)
    if found is None:
        return ""
    name, n = found
    return f"{name.upper()} appears in {n} of the 3 priority actions"


def action_headline(action: dict[str, Any]) -> str:
    lever = _text(action.get("lever")).upper()
    gap = parse_store_gap(action)
    retailer = _text(action.get("retailer"))
    if lever == "DISTRIBUTION" and gap > 0:
        return f"Close the {gap:.0f}-store distribution gap"
    if lever == "PRICE":
        return f"Test price position at {retailer}" if retailer else "Test like-for-like price position"
    if lever == "PROMOTION":
        return f"Target promotion at {retailer}" if retailer else "Target a promotion test"
    if lever == "MULTI-LEVER" and gap > 0:
        return f"Close the {gap:.0f}-store gap and support with promotion"
    return _text(action.get("headline")) or "Brief the named commercial action"


def recommended_action(action: dict[str, Any]) -> str:
    lever = _text(action.get("lever")).upper()
    product = _text(action.get("product"))
    retailer = _text(action.get("retailer"))
    region = _text(action.get("region"))
    gap = parse_store_gap(action)
    if lever == "DISTRIBUTION" and gap > 0:
        return (
            f"Close the {gap:.0f}-store gap toward the like-for-like benchmark at {retailer}. "
            f"Expand listing of {product} across the identified {retailer} stores in {region}."
        )
    if lever == "PRICE":
        return (
            f"Run a like-for-like price test for {product} at {retailer} in {region}. "
            f"Do not discount solely because sales are low."
        )
    if lever == "PROMOTION":
        return (
            f"Test promotion for {product} at {retailer} in {region} where distribution is adequate. "
            f"Treat the result as directional, not booked incrementality."
        )
    source = _text(action.get("recommended_action"))
    return source or f"Brief {product} at {retailer} in {region}."


def build_headline(actions: list[dict[str, Any]], lever: str) -> str:
    found = repeating_retailer(actions)
    levers = {_text(item.get("lever")).upper() for item in actions}
    if levers == {"DISTRIBUTION"} and found is not None:
        retailer, _n = found
        return f"Distribution gaps — led by {retailer} — are the clearest near-term growth opportunity"
    if levers == {"DISTRIBUTION"}:
        return "Distribution is the clearest growth lever in the current priority opportunities"
    if levers == {"PRICE"}:
        return "Like-for-like price tests are the clearest next commercial move"
    if levers == {"PROMOTION"}:
        return "Targeted promotion tests are the clearest next commercial move"
    if lever == "DISTRIBUTION":
        return "Distribution is the clearest growth lever in the current priority opportunities"
    if lever == "PRICE":
        return "Like-for-like price tests, not blanket discounting, are the next lever"
    if lever == "PROMOTION":
        return "Promotion is the near-term lever to test on the named grains"
    return "A small set of named actions is the clearest near-term commercial move"


def build_subheadline(actions: list[dict[str, Any]], lever: str) -> str:
    n = len(actions)
    n_word = {1: "One", 2: "Two", 3: "Three"}.get(n, str(n))
    value = sum(addressable_value(item) for item in actions)
    volume = sum(addressable_volume(item) for item in actions)
    confs = {_text(item.get("confidence")).upper() for item in actions}
    conf_txt = "high-confidence " if confs == {"HIGH"} else ""
    lever_txt = {
        "DISTRIBUTION": "distribution gaps",
        "PRICE": "price tests",
        "PROMOTION": "promotion tests",
        "MULTI-LEVER": "multi-lever actions",
    }.get(lever, "priority actions")
    if len({_text(item.get("lever")).upper() for item in actions}) > 1:
        lever_txt = "priority actions"
    return (
        f"{n_word} {conf_txt}{lever_txt} represent {_rand_compact(value)} of addressable value and "
        f"{volume:,.0f} units across priority SKU-retailer-region combinations."
    ).replace("  ", " ")


def key_insight(actions: list[dict[str, Any]], lever: str) -> str:
    found = repeating_retailer(actions)
    if lever == "DISTRIBUTION" and found is not None:
        retailer, n = found
        return (
            f"{retailer} accounts for {n} of the 3 priority actions, so listing expansion is the first "
            f"commercial move rather than a price cut or extra promotional spend."
        )
    if lever == "DISTRIBUTION":
        return (
            "Availability is the primary constraint on the named grains, so distribution expansion "
            "comes before price or promotion intervention."
        )
    if lever == "PRICE":
        return (
            "Coverage is adequate on the named grains; the next move is a like-for-like price test, "
            "not a promotion or a blanket discount."
        )
    if lever == "PROMOTION":
        return (
            "Distribution is adequate on the named grains; the next move is a targeted promotion test, "
            "not a price cut because sales are low."
        )
    return (
        "The three named actions are the story; overlapping specialist values are not added together "
        "and results remain addressable opportunity, not guaranteed incremental sales."
    )


def commercial_implication(actions: list[dict[str, Any]], lever: str) -> str:
    levers = {_text(item.get("lever")).upper() for item in actions}
    if levers == {"DISTRIBUTION"}:
        return (
            "Prioritize distribution expansion before increasing promotional spend where availability "
            "is the primary constraint."
        )
    if levers == {"PRICE"}:
        return "Run like-for-like price tests on the named grains; do not discount solely because sales are low."
    if levers == {"PROMOTION"}:
        return (
            "Test the named promotions where distribution is already adequate; treat results as directional, "
            "not booked incrementality."
        )
    if lever == "DISTRIBUTION":
        return (
            "Act first on the named distribution gaps; do not treat price or promotion as a substitute "
            "where availability is the constraint."
        )
    return "Brief the three named actions in rank order; do not add overlapping specialist values together."


def data_coverage(_slide: dict[str, Any]) -> str:
    return DEFAULT_DATA_COVERAGE


def limitations(slide: dict[str, Any]) -> list[str]:
    notes = list(V1_LIMITATIONS)
    for item in slide.get("limitations") or []:
        text = str(item).strip()
        if text and text not in notes:
            notes.append(text)
    return notes


def build_story(slide: dict[str, Any]) -> OneSlideStory:
    raw_actions = [item for item in (slide.get("top_actions") or []) if isinstance(item, dict)]
    raw_actions = sorted(raw_actions, key=lambda item: int(item.get("rank") or 0))[:3]
    if len(raw_actions) != 3:
        raise ValueError("Commercial Brain one-slide must contain exactly three actions")
    lever = dominant_lever(raw_actions)
    cards: list[StoryAction] = []
    for item in raw_actions:
        confidence = _text(item.get("confidence")).upper() or "LOW"
        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "LOW"
        cards.append(
            StoryAction(
                rank=int(item.get("rank") or len(cards) + 1),
                lever=_text(item.get("lever")),
                headline=action_headline(item),
                product=_text(item.get("product")),
                brand=None if not _text(item.get("brand")) else _text(item.get("brand")),
                retailer=_text(item.get("retailer")),
                region=_text(item.get("region")),
                addressable_value=addressable_value(item),
                addressable_volume=addressable_volume(item),
                confidence=confidence,  # type: ignore[arg-type]
                store_gap=parse_store_gap(item),
                recommended_action=recommended_action(item),
            )
        )
    total_value = _num(
        slide.get("total_addressable_value_opportunity", slide.get("total_estimated_value_opportunity"))
    )
    total_volume = _num(
        slide.get("total_addressable_volume_opportunity", slide.get("total_estimated_volume_opportunity"))
    )
    headline = build_headline(raw_actions, lever)
    return OneSlideStory(
        title="Unilever commercial story",
        headline=headline,
        subheadline=build_subheadline(raw_actions, lever),
        hero_metric=HeroMetric(label="Addressable value", value=total_value, unit="R"),
        hero_volume=HeroMetric(label="Addressable volume", value=total_volume, unit="units"),
        dominant_lever=lever,
        key_insight=key_insight(raw_actions, lever),
        retailer_insight=retailer_insight(raw_actions),
        actions=cards,
        commercial_implication=commercial_implication(raw_actions, lever),
        methodology_note=METHODOLOGY_NOTE,
        data_coverage=data_coverage(slide),
        limitations=limitations(slide),
        macro_context=absent_macro_context(),
    )


def assert_no_unsupported_claims(story: OneSlideStory) -> None:
    macro = story.macro_context
    blob = " ".join(
        [
            story.headline,
            story.subheadline,
            story.key_insight,
            story.retailer_insight,
            story.commercial_implication,
            story.methodology_note,
            " ".join(item.headline + " " + item.recommended_action for item in story.actions),
            macro.supporting_line,
            macro.signal or "",
            macro.evidence or "",
            macro.commercial_implication or "",
            macro.causality_disclaimer,
        ]
    ).lower()
    if "guaranteed incremental sales" in blob and "not guaranteed incremental sales" not in blob:
        raise ValueError("Story claims guaranteed incremental sales")
    for phrase in _CAUSAL_FORBIDDEN:
        if phrase == "guaranteed incremental sales":
            continue
        if phrase in blob:
            raise ValueError(f"Unsupported causal language: {phrase}")
