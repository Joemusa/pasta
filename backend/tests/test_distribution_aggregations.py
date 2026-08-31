"""Retailer / region / SKU roll-ups ranked by opportunity, not current sales."""

from __future__ import annotations

from backend.agents.distribution.aggregations import aggregate_opportunities
from backend.agents.distribution.models import Opportunity


def _opp(**overrides: object) -> Opportunity:
    payload = {
        "opportunity_id": "id",
        "sku": "SKU-A",
        "retailer": "Retailer A",
        "region": "Gauteng",
        "current_stores": 5.0,
        "benchmark_stores": 10.0,
        "store_gap": 5.0,
        "value_per_store": 10.0,
        "volume_per_store": 1.0,
        "value_opportunity": 50.0,
        "volume_opportunity": 5.0,
        "benchmark_type": "recent_high",
        "confidence": "MEDIUM",
        "period": "2026-08-16",
        "benchmark_confidence": "MEDIUM",
    }
    payload.update(overrides)
    return Opportunity.model_validate(payload)


def test_retailer_region_sku_aggregation() -> None:
    opps = [
        _opp(
            opportunity_id="1",
            sku="SKU-A",
            retailer="Needle",
            region="Gauteng",
            value_opportunity=100,
            volume_opportunity=10,
            store_gap=4,
        ),
        _opp(
            opportunity_id="2",
            sku="SKU-B",
            retailer="Needle",
            region="Western Cape",
            value_opportunity=80,
            volume_opportunity=8,
            store_gap=3,
        ),
        _opp(
            opportunity_id="3",
            sku="SKU-A",
            retailer="Quiet",
            region="Gauteng",
            value_opportunity=10,
            volume_opportunity=1,
            store_gap=1,
        ),
    ]
    retailers, regions, skus = aggregate_opportunities(opps)
    assert retailers[0].name == "Needle"
    assert retailers[0].total_value_opportunity == 180.0
    assert retailers[0].affected_skus == 2
    assert retailers[0].affected_regions == 2
    assert retailers[0].affected_stores == 7.0
    assert regions[0].name == "Gauteng"
    assert skus[0].name == "SKU-A"
    assert skus[0].affected_retailers == 2


def test_ranking_is_not_by_current_sales() -> None:
    opps = [
        _opp(
            opportunity_id="big-gap",
            sku="SKU-X",
            retailer="Small Banner",
            region="Limpopo",
            value_opportunity=500,
            volume_opportunity=40,
            store_gap=20,
            confidence="HIGH",
        ),
        _opp(
            opportunity_id="tiny-gap",
            sku="SKU-Y",
            retailer="National Chain",
            region="Gauteng",
            value_opportunity=5,
            volume_opportunity=1,
            store_gap=1,
            confidence="LOW",
        ),
    ]
    sales = {
        ("retailer", "National Chain"): 9_000_000.0,
        ("retailer", "Small Banner"): 1_000.0,
    }
    retailers, _regions, _skus = aggregate_opportunities(opps, sales)
    assert [item.name for item in retailers] == ["Small Banner", "National Chain"]
    assert retailers[0].current_sales_value == 1000.0
    assert retailers[1].current_sales_value == 9_000_000.0
