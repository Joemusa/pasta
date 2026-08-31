"""Dashboard V1 presentation tests. Frozen specialist calculations must not be recalculated."""

from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from backend.dashboard.jsonutil import json_safe
from backend.dashboard.loader import load_store
from backend.dashboard.query import assemble, filter_options, opportunity_detail
from backend.dashboard.server import DashboardHandler

EXPECTED_VALUE = 588562.67
EXPECTED_VOLUME = 14521.165


@pytest.fixture(scope="module")
def store():
    return load_store("backend/data")


def _dump(payload: dict) -> str:
    return json.dumps(json_safe(payload), allow_nan=False)


def _assert_clean(payload: dict) -> None:
    blob = _dump(payload)
    assert "NaN" not in blob
    assert "Infinity" not in blob
    assert "undefined" not in blob.lower()


def test_default_filters_match_brain_totals(store) -> None:
    payload = assemble(store)
    kpis = payload["kpis"]
    assert kpis["addressable_value"]["available"] is True
    assert kpis["addressable_value"]["value"] == pytest.approx(EXPECTED_VALUE)
    assert kpis["addressable_volume"]["value"] == pytest.approx(EXPECTED_VOLUME)
    assert kpis["sales_quantity"]["available"] is False
    assert kpis["sales_quantity"]["display"] == "Not available"
    assert kpis["price_per_kg"]["available"] is False
    assert kpis["sales_value"]["available"] is True
    assert kpis["sales_value"]["value"] != 0
    assert payload["story"]["headline"]
    assert "Distribution" in payload["story"]["headline"]
    assert len(payload["top_actions"]) == 3
    assert len(payload["trends"]["sales_value"]) == store.pos_weeks == 4
    assert "not a 12-month trend" in payload["trends"]["note"].lower()
    assert payload["quality"]["period_list"] == store.period_list
    assert payload["quality"]["current_period"] == "2026-08-16"
    assert payload["macro"]["role"] == "supporting_context"
    assert payload["social"]["status"]
    _assert_clean(payload)


def test_select_one_region_updates_kpis_and_story(store) -> None:
    default = assemble(store)
    region = next(item["name"] for item in default["regions"])
    payload = assemble(store, region=region)
    assert payload["filters"]["region"] == region
    assert payload["kpis"]["sales_value"]["value"] != default["kpis"]["sales_value"]["value"]
    assert payload["kpis"]["addressable_value"]["value"] != default["kpis"]["addressable_value"]["value"]
    assert all(item["region"] == region for item in payload["opportunities"])
    assert payload["story"]["headline"] != default["story"]["headline"] or payload["top_actions"][0]["region"] == region
    assert region in payload["options"]["region"]
    _assert_clean(payload)


def test_select_one_retailer_updates_ranking(store) -> None:
    default = assemble(store)
    retailer = next(item["name"] for item in default["retailers"])
    payload = assemble(store, retailer=retailer)
    assert payload["kpis"]["sales_value"]["value"] != default["kpis"]["sales_value"]["value"]
    assert all(item["retailer"] == retailer for item in payload["opportunities"])
    assert payload["kpis"]["addressable_value"]["available"] is True
    _assert_clean(payload)


def test_select_one_brand_cascades_products(store) -> None:
    brand = "Sunlight"
    payload = assemble(store, brand=brand)
    options = filter_options(store, {"brand": brand})
    assert options["product"]
    pos_products = set(store.pos.loc[store.pos["brand"].astype(str) == brand, "product"].astype(str))
    assert set(options["product"]) <= pos_products
    assert "Sunlight" in options["brand"]
    assert payload["kpis"]["sales_value"]["available"] is True
    assert all(item["brand"] == brand for item in payload["opportunities"])
    _assert_clean(payload)


def test_select_one_product_narrows_kpis(store) -> None:
    default = assemble(store)
    product = default["top_actions"][0]["product"]
    payload = assemble(store, product=product)
    assert payload["filters"]["product"] == product
    assert payload["kpis"]["sales_value"]["value"] < default["kpis"]["sales_value"]["value"]
    assert all(item["product"] == product for item in payload["opportunities"])
    assert payload["story"]["headline"]
    _assert_clean(payload)


@pytest.mark.parametrize("lever", ["DISTRIBUTION", "PRICE", "PROMOTION"])
def test_select_commercial_lever(store, lever: str) -> None:
    default = assemble(store)
    payload = assemble(store, lever=lever)
    assert payload["filters"]["lever"] == lever
    assert all(item["lever"] == lever for item in payload["opportunities"])
    if lever != "DISTRIBUTION":
        assert payload["kpis"]["addressable_value"]["value"] != default["kpis"]["addressable_value"]["value"]
        assert payload["story"]["dominant_lever"] == lever
    assert payload["kpis"]["sales_value"]["value"] == default["kpis"]["sales_value"]["value"]
    if lever == "PRICE":
        assert payload["price"]
        assert payload["distribution"] == []
        assert payload["promotion"] == []
        assert "price" in payload["story"]["headline"].lower()
    if lever == "PROMOTION":
        assert payload["distribution"] == []
        assert payload["price"] == []
        assert "promotion" in payload["story"]["headline"].lower()
    if lever == "DISTRIBUTION":
        assert payload["distribution"]
        assert payload["price"] == []
        assert "distribution" in payload["story"]["headline"].lower()
    _assert_clean(payload)


def test_reset_filters_restores_default(store) -> None:
    default = assemble(store)
    filtered = assemble(store, region=default["regions"][0]["name"], lever="PRICE")
    reset = assemble(store)
    assert reset["kpis"]["addressable_value"]["value"] == default["kpis"]["addressable_value"]["value"]
    assert reset["story"]["headline"] == default["story"]["headline"]
    assert [item["opportunity_id"] for item in reset["top_actions"]] == [
        item["opportunity_id"] for item in default["top_actions"]
    ]
    assert filtered["kpis"]["addressable_value"]["value"] != default["kpis"]["addressable_value"]["value"]
    _assert_clean(reset)


def test_top_ten_uses_brain_priority_order(store) -> None:
    payload = assemble(store, top_n=10)
    assert len(payload["opportunities"]) == 10
    assert len(payload["top_actions"]) == 3
    scores = [item["priority_score"] for item in payload["opportunities"]]
    assert scores == sorted(scores, reverse=True)


def test_missing_metrics_are_not_zero_filled(store) -> None:
    payload = assemble(store)
    assert payload["kpis"]["sales_quantity"]["value"] is None
    assert payload["kpis"]["price_per_kg"]["value"] is None
    for row in payload["price"][:5]:
        assert row["price_per_kg"]["available"] is False
        assert row["normal_price"]["available"] is False
        assert row["normal_price"]["display"] == "Not available"
    for row in payload["promotion"][:5]:
        if row["normal_price"]["value"] is None:
            assert row["normal_price"]["display"] == "Not available"


def test_confidence_is_not_upgraded(store) -> None:
    low = next(item for item in store.opportunities if item.confidence == "LOW")
    payload = assemble(store, product=low.product, retailer=low.retailer, region=low.region)
    confs = {item["confidence"] for item in payload["opportunities"]}
    assert "LOW" in confs or not payload["opportunities"]
    detail = opportunity_detail(store, low.opportunity_id)
    assert detail is not None
    assert detail["confidence"] == "LOW"
    assert detail["double_counting_risk"]


def test_historical_period_hides_addressable_opportunity(store) -> None:
    past = store.period_list[0]
    assert past != store.current_period
    payload = assemble(store, period=past)
    assert payload["kpis"]["addressable_value"]["available"] is False
    assert payload["kpis"]["addressable_value"]["display"] == "Not available"
    assert payload["opportunities"] == []
    assert payload["kpis"]["sales_value"]["available"] is True


def test_primary_lever_sum_matches_brain_and_avoids_specialist_stacking(store) -> None:
    payload = assemble(store)
    summed = sum(item.addressable_value_opportunity for item in store.opportunities)
    assert payload["kpis"]["addressable_value"]["value"] == pytest.approx(summed)
    assert summed == pytest.approx(EXPECTED_VALUE)


def test_http_dashboard_and_detail_endpoints(store) -> None:
    DashboardHandler.store = store
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    try:
        import urllib.parse
        import urllib.request

        with urllib.request.urlopen(f"http://{host}:{port}/api/health") as response:
            health = json.loads(response.read().decode())
        assert health["status"] == "ok"
        with urllib.request.urlopen(f"http://{host}:{port}/api/dashboard") as response:
            payload = json.loads(response.read().decode())
        assert payload["kpis"]["addressable_value"]["value"] == pytest.approx(EXPECTED_VALUE)
        opp_id = payload["top_actions"][0]["opportunity_id"]
        encoded = urllib.parse.quote(opp_id)
        with urllib.request.urlopen(f"http://{host}:{port}/api/opportunity?id={encoded}") as response:
            detail = json.loads(response.read().decode())
        assert detail["opportunity_id"] == opp_id
        with urllib.request.urlopen(f"http://{host}:{port}/") as response:
            html = response.read().decode()
        assert "Commercial Intelligence" in html
    finally:
        httpd.shutdown()
        httpd.server_close()
