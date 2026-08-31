"""Retailer, SKU, and region roll-ups of primary-lever value only."""

from __future__ import annotations

from collections import defaultdict

from backend.agents.brain.models import BrainMover, BrainOpportunity, BrainSkuPriority

_SCORE = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _avg_confidence(scores: list[str]) -> str:
    if not scores:
        return "LOW"
    mean = sum(_SCORE.get(item, 1) for item in scores) / len(scores)
    if mean >= 2.5:
        return "HIGH"
    if mean >= 1.5:
        return "MEDIUM"
    return "LOW"


def _dominant_from_value(by_lever: dict[str, float]) -> str:
    if not by_lever:
        return "INSUFFICIENT EVIDENCE"
    return max(by_lever.items(), key=lambda item: (item[1], item[0]))[0]


def aggregate_movers(
    opportunities: list[BrainOpportunity],
) -> tuple[list[BrainMover], list[BrainMover]]:
    return (
        _rank(_bucket(opportunities, "retailer"), kind="retailer"),
        _rank(_bucket(opportunities, "region"), kind="region"),
    )


def sku_priorities(opportunities: list[BrainOpportunity], top_n: int) -> list[BrainSkuPriority]:
    ranked = sorted(
        opportunities,
        key=lambda item: (-item.priority_score, -item.opportunity_value, item.product, item.retailer),
    )
    return [
        BrainSkuPriority(
            product=item.product,
            brand=item.brand,
            retailer=item.retailer,
            region=item.region,
            dominant_lever=item.dominant_lever,
            opportunity_value=item.opportunity_value,
            opportunity_volume=item.opportunity_volume,
            addressable_value_opportunity=item.addressable_value_opportunity,
            addressable_volume_opportunity=item.addressable_volume_opportunity,
            current_sales=item.current_sales,
            sales_per_store=item.sales_per_store,
            distribution=item.distribution_stores,
            price_signal=item.price_signal,
            promotion_signal=item.promotion_signal,
            priority_score=item.priority_score,
            confidence=item.confidence,
            recommended_action=item.recommended_action,
        )
        for item in ranked[:top_n]
    ]


def _bucket(opportunities: list[BrainOpportunity], key: str) -> dict[str, dict[str, object]]:
    buckets: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "value": 0.0,
            "volume": 0.0,
            "skus": set(),
            "regions": set(),
            "retailers": set(),
            "n": 0,
            "conf": [],
            "lever_value": defaultdict(float),
            "top_sku": ("", 0.0),
            "top_retailer": ("", 0.0),
        }
    )
    for opp in opportunities:
        name = str(getattr(opp, key))
        bucket = buckets[name]
        bucket["value"] = float(bucket["value"]) + opp.opportunity_value
        bucket["volume"] = float(bucket["volume"]) + opp.opportunity_volume
        skus = bucket["skus"]
        regions = bucket["regions"]
        retailers = bucket["retailers"]
        conf = bucket["conf"]
        lever_value = bucket["lever_value"]
        assert isinstance(skus, set)
        assert isinstance(regions, set)
        assert isinstance(retailers, set)
        assert isinstance(conf, list)
        assert isinstance(lever_value, defaultdict)
        skus.add(opp.product)
        regions.add(opp.region)
        retailers.add(opp.retailer)
        conf.append(opp.confidence)
        lever_value[opp.dominant_lever] = float(lever_value[opp.dominant_lever]) + opp.opportunity_value
        bucket["n"] = int(bucket["n"]) + 1
        top_sku = bucket["top_sku"]
        top_retailer = bucket["top_retailer"]
        assert isinstance(top_sku, tuple)
        assert isinstance(top_retailer, tuple)
        if opp.opportunity_value >= float(top_sku[1]):
            bucket["top_sku"] = (opp.product, opp.opportunity_value)
        if opp.opportunity_value >= float(top_retailer[1]):
            bucket["top_retailer"] = (opp.retailer, opp.opportunity_value)
    return buckets


def _rank(buckets: dict[str, dict[str, object]], *, kind: str) -> list[BrainMover]:
    movers: list[BrainMover] = []
    for name, bucket in buckets.items():
        skus = bucket["skus"]
        regions = bucket["regions"]
        retailers = bucket["retailers"]
        conf = bucket["conf"]
        lever_value = bucket["lever_value"]
        assert isinstance(skus, set)
        assert isinstance(regions, set)
        assert isinstance(retailers, set)
        assert isinstance(conf, list)
        assert isinstance(lever_value, defaultdict)
        mix = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for item in conf:
            mix[str(item)] = mix.get(str(item), 0) + 1
        dominant = _dominant_from_value({str(k): float(v) for k, v in lever_value.items()})
        top_sku = bucket["top_sku"]
        top_retailer = bucket["top_retailer"]
        assert isinstance(top_sku, tuple)
        assert isinstance(top_retailer, tuple)
        action = None
        if kind == "region":
            action = f"Prioritise {dominant.lower()} interventions in {name}"
        elif kind == "retailer":
            action = f"Move the needle at {name} via {dominant.lower()}"
        movers.append(
            BrainMover(
                name=name,
                estimated_value=round(float(bucket["value"]), 2),
                estimated_volume=round(float(bucket["volume"]), 4),
                addressable_value=round(float(bucket["value"]), 2),
                addressable_volume=round(float(bucket["volume"]), 4),
                dominant_lever=dominant,
                opportunities=int(bucket["n"]),
                skus=len(skus),
                regions=len(regions),
                retailers=len(retailers),
                evidence_strength=_avg_confidence([str(item) for item in conf]),
                confidence_mix=mix,
                recommended_action=action,
                top_retailer=str(top_retailer[0]) or None,
                top_sku=str(top_sku[0]) or None,
            )
        )
    movers.sort(key=lambda item: (-item.estimated_value, -item.estimated_volume, -item.opportunities, item.name))
    return movers
