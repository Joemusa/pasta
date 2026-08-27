from __future__ import annotations

from backend.agents.data_qa.models import load_canonical_schema
from backend.agents.data_qa.schema_detector import apply_mapping, detect_columns, normalize_name
from backend.tests.helpers import canonical_rows


def test_normalize_collapses_punctuation() -> None:
    assert normalize_name("Trended Ave Price (Value/Volume)") == "trended ave price value volume"
    assert normalize_name("% Time on Promo") == "percent time on promo"


def test_discovery_style_headers_map_to_canonical() -> None:
    schema = load_canonical_schema()
    frame = canonical_rows().rename(
        columns={
            "date": "DDMMMYY",
            "sales_value": "4 Weeks CY Value",
            "sales_volume": "4 Weeks CY Volume",
            "store_count": "4 Weeks Store Count",
            "current_price": "4 Weeks CY Ave Price Quantity",
            "percent_time_on_promo": "CY % Time On Promo",
            "percent_sales_on_promo": "4 Weeks CY % Sales On Promo",
        }
    )
    mapping = detect_columns(frame, schema)
    assert mapping.source_to_canonical["DDMMMYY"] == "date"
    assert mapping.source_to_canonical["4 Weeks CY Value"] == "sales_value"
    assert mapping.source_to_canonical["4 Weeks CY Volume"] == "sales_volume"
    assert mapping.source_to_canonical["4 Weeks Store Count"] == "store_count"
    assert mapping.source_to_canonical["4 Weeks CY Ave Price Quantity"] == "current_price"
    assert mapping.source_to_canonical["CY % Time On Promo"] == "percent_time_on_promo"
    assert mapping.source_to_canonical["4 Weeks CY % Sales On Promo"] == "percent_sales_on_promo"


def test_maps_nielsen_style_headers() -> None:
    schema = load_canonical_schema()
    frame = canonical_rows().rename(
        columns={
            "date": "MonthYear2",
            "manufacturer": "Manufacturer",
            "product": "Product",
            "sales_value": "Trended Sales Value",
            "sales_volume": "Trended Sales Volume",
            "current_price": "Trended Ave Price (Value/Volume)",
        }
    )
    mapping = detect_columns(frame, schema)
    assert mapping.source_to_canonical["MonthYear2"] == "date"
    assert mapping.source_to_canonical["Trended Sales Value"] == "sales_value"
    assert mapping.source_to_canonical["Trended Ave Price (Value/Volume)"] == "current_price"
    mapped = apply_mapping(frame, mapping)
    assert "date" in mapped.columns
    assert "sales_value" in mapped.columns


def test_alias_collision_keeps_first_canonical_mapping() -> None:
    schema = load_canonical_schema()
    frame = canonical_rows()[["date", "product", "sku", "retailer", "sales_value", "sales_volume"]].copy()
    frame["Item"] = frame["product"]
    mapping = detect_columns(frame, schema)
    assert mapping.source_to_canonical["product"] == "product"
    assert "Item" in mapping.unmapped_source_columns or mapping.source_to_canonical.get("Item") != "product"


def test_constant_retailer_is_injected() -> None:
    schema = load_canonical_schema()
    frame = canonical_rows().drop(columns=["retailer"])
    mapping = detect_columns(frame, schema)
    mapped = apply_mapping(frame, mapping, constant_columns={"retailer": "National panel"})
    assert (mapped["retailer"] == "National panel").all()
