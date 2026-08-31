"""Retailer, SKU, and region roll-ups for estimated promotional opportunities."""

from __future__ import annotations

from collections import defaultdict

from backend.agents.promotion.models import PromoMover, PromotionOpportunity

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


def aggregate_opportunities(
    opportunities: list[PromotionOpportunity],
) -> tuple[list[PromoMover], list[PromoMover], list[PromoMover]]:
    return (
        _rank(_bucket(opportunities, "retailer")),
        _rank(_bucket(opportunities, "product")),
        _rank(_bucket(opportunities, "region")),
    )


def _bucket(opportunities: list[PromotionOpportunity], key: str) -> dict[str, dict[str, object]]:
    buckets: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "value": 0.0,
            "volume": 0.0,
            "skus": set(),
            "regions": set(),
            "retailers": set(),
            "n": 0,
            "conf": [],
            "uplift": [],
        }
    )
    for opp in opportunities:
        name = getattr(opp, key)
        bucket = buckets[str(name)]
        bucket["value"] = float(bucket["value"]) + opp.estimated_incremental_value
        bucket["volume"] = float(bucket["volume"]) + opp.estimated_incremental_volume
        skus = bucket["skus"]
        regions = bucket["regions"]
        retailers = bucket["retailers"]
        conf = bucket["conf"]
        uplift = bucket["uplift"]
        assert isinstance(skus, set)
        assert isinstance(regions, set)
        assert isinstance(retailers, set)
        assert isinstance(conf, list)
        assert isinstance(uplift, list)
        skus.add(opp.product)
        regions.add(opp.region)
        retailers.add(opp.retailer)
        conf.append(opp.confidence)
        if opp.volume_uplift_pct is not None:
            uplift.append(opp.volume_uplift_pct)
        bucket["n"] = int(bucket["n"]) + 1
    return buckets


def _rank(buckets: dict[str, dict[str, object]]) -> list[PromoMover]:
    movers: list[PromoMover] = []
    for name, bucket in buckets.items():
        skus = bucket["skus"]
        regions = bucket["regions"]
        retailers = bucket["retailers"]
        conf = bucket["conf"]
        uplift = bucket["uplift"]
        assert isinstance(skus, set)
        assert isinstance(regions, set)
        assert isinstance(retailers, set)
        assert isinstance(conf, list)
        assert isinstance(uplift, list)
        mix = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for item in conf:
            mix[str(item)] = mix.get(str(item), 0) + 1
        avg_uplift = None if not uplift else round(sum(float(item) for item in uplift) / len(uplift), 4)
        movers.append(
            PromoMover(
                name=name,
                estimated_incremental_value=round(float(bucket["value"]), 2),
                estimated_incremental_volume=round(float(bucket["volume"]), 4),
                skus=len(skus),
                regions=len(regions),
                retailers=len(retailers),
                opportunities=int(bucket["n"]),
                average_uplift=avg_uplift,
                average_confidence=_avg_confidence([str(item) for item in conf]),
                confidence_mix=mix,
            )
        )
    movers.sort(
        key=lambda item: (
            -item.estimated_incremental_value,
            -item.estimated_incremental_volume,
            -item.opportunities,
            item.name,
        )
    )
    return movers
