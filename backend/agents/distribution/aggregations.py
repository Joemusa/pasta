"""Retailer, region, and SKU roll-ups ranked by opportunity, not current sales."""

from __future__ import annotations

from collections import defaultdict

from backend.agents.distribution.models import NeedleMover, Opportunity


def _priority(confidence: str) -> bool:
    return confidence in {"HIGH", "MEDIUM"}


def aggregate_opportunities(
    opportunities: list[Opportunity],
    current_sales: dict[tuple[str, str], float] | None = None,
) -> tuple[list[NeedleMover], list[NeedleMover], list[NeedleMover]]:
    """Return ranked retailer, region, and SKU movers."""
    retailers = _bucket(opportunities, "retailer", current_sales, sales_dim="retailer")
    regions = _bucket(opportunities, "region", current_sales, sales_dim="region")
    skus = _bucket(opportunities, "sku", current_sales, sales_dim="sku")
    return (
        _rank(retailers, fourth="priority_skus"),
        _rank(regions, fourth="priority_skus"),
        _rank(skus, fourth="affected_retailers"),
    )


def _bucket(
    opportunities: list[Opportunity],
    key: str,
    current_sales: dict[tuple[str, str], float] | None,
    *,
    sales_dim: str,
) -> dict[str, dict[str, float | int | set[str]]]:
    buckets: dict[str, dict[str, float | int | set[str]]] = defaultdict(
        lambda: {
            "total_value_opportunity": 0.0,
            "total_volume_opportunity": 0.0,
            "affected_stores": 0.0,
            "skus": set(),
            "regions": set(),
            "retailers": set(),
            "priority_skus": set(),
            "current_sales_value": 0.0,
        }
    )
    for opp in opportunities:
        name = getattr(opp, key)
        bucket = buckets[name]
        bucket["total_value_opportunity"] = float(bucket["total_value_opportunity"]) + opp.value_opportunity
        bucket["total_volume_opportunity"] = float(bucket["total_volume_opportunity"]) + opp.volume_opportunity
        bucket["affected_stores"] = float(bucket["affected_stores"]) + opp.store_gap
        skus = bucket["skus"]
        regions = bucket["regions"]
        retailers = bucket["retailers"]
        assert isinstance(skus, set)
        assert isinstance(regions, set)
        assert isinstance(retailers, set)
        skus.add(opp.sku)
        regions.add(opp.region)
        retailers.add(opp.retailer)
        if _priority(opp.confidence):
            priority = bucket["priority_skus"]
            assert isinstance(priority, set)
            priority.add(opp.sku)
    if current_sales:
        for (dim, name), value in current_sales.items():
            if dim == sales_dim and name in buckets:
                buckets[name]["current_sales_value"] = value
    return buckets


def _rank(buckets: dict[str, dict[str, float | int | set[str]]], *, fourth: str) -> list[NeedleMover]:
    movers: list[NeedleMover] = []
    for name, bucket in buckets.items():
        skus = bucket["skus"]
        regions = bucket["regions"]
        retailers = bucket["retailers"]
        priority = bucket["priority_skus"]
        assert isinstance(skus, set)
        assert isinstance(regions, set)
        assert isinstance(retailers, set)
        assert isinstance(priority, set)
        movers.append(
            NeedleMover(
                name=name,
                total_value_opportunity=round(float(bucket["total_value_opportunity"]), 2),
                total_volume_opportunity=round(float(bucket["total_volume_opportunity"]), 4),
                affected_skus=len(skus),
                affected_regions=len(regions),
                affected_retailers=len(retailers),
                affected_stores=round(float(bucket["affected_stores"]), 2),
                priority_skus=len(priority),
                current_sales_value=round(float(bucket["current_sales_value"]), 2),
            )
        )

    def sort_key(item: NeedleMover) -> tuple[float, float, float, int]:
        fourth_value = item.priority_skus if fourth == "priority_skus" else item.affected_retailers
        return (
            -item.total_value_opportunity,
            -item.total_volume_opportunity,
            -item.affected_stores,
            -fourth_value,
        )

    movers.sort(key=sort_key)
    return movers
