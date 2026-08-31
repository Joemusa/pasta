"""End-to-end Distribution Agent tests on cleaned Unilever-shaped tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.agents.distribution import run_distribution
from backend.agents.distribution.__main__ import build_parser
from backend.agents.distribution.loader import DistributionLoadError


def _clean_frame() -> pd.DataFrame:
    """Four-week Unilever extract plus a competitor row that must be ignored."""
    rows: list[dict[str, object]] = []
    weeks = ["2026-07-26", "2026-08-02", "2026-08-09", "2026-08-16"]
    # SKU A listed in four regions of the same retailer; Western Cape is under-distributed.
    for date in weeks:
        for region, stores, value, volume in [
            ("Gauteng", 12, 1200, 120),
            ("KwaZulu-Natal", 11, 1100, 110),
            ("Eastern Cape", 10, 1000, 100),
            (
                "Western Cape",
                4 if date != "2026-08-02" else 16,
                400 if date != "2026-08-02" else 1600,
                40 if date != "2026-08-02" else 160,
            ),
        ]:
            rows.append(
                {
                    "date": date,
                    "manufacturer": "Unilever",
                    "product": "Handy Andy All Purpose Cleaner Lemon 750ml",
                    "retailer": "Checkers",
                    "region": region,
                    "sales_value": value,
                    "sales_volume": volume,
                    "store_count": stores,
                }
            )
    # Zero-store current listing with peer coverage.
    rows.append(
        {
            "date": "2026-08-16",
            "manufacturer": "Unilever",
            "product": "Sunlight Pine Gel 1l",
            "retailer": "Spar",
            "region": "Limpopo",
            "sales_value": 0,
            "sales_volume": 0,
            "store_count": 0,
        }
    )
    for region, stores, value, volume in [
        ("Gauteng", 8, 800, 80),
        ("Western Cape", 7, 700, 70),
        ("Eastern Cape", 9, 900, 90),
    ]:
        rows.append(
            {
                "date": "2026-08-16",
                "manufacturer": "Unilever",
                "product": "Sunlight Pine Gel 1l",
                "retailer": "Spar",
                "region": region,
                "sales_value": value,
                "sales_volume": volume,
                "store_count": stores,
            }
        )
    # Missing store count should be skipped, not filled with zero.
    rows.append(
        {
            "date": "2026-08-16",
            "manufacturer": "Unilever",
            "product": "Domestos Surface Wipes 40ea",
            "retailer": "Game",
            "region": "Free State",
            "sales_value": 50,
            "sales_volume": 2,
            "store_count": pd.NA,
        }
    )
    # Competitor must not enter Unilever opportunities.
    rows.append(
        {
            "date": "2026-08-16",
            "manufacturer": "Reckitt Benckiser",
            "product": "Dettol All Purpose Cleaner Citrus 1.5l",
            "retailer": "Checkers",
            "region": "Gauteng",
            "sales_value": 9999,
            "sales_volume": 999,
            "store_count": 99,
        }
    )
    return pd.DataFrame(rows)


def test_agent_uses_latest_period_and_unilever_only(tmp_path: Path) -> None:
    clean_dir = tmp_path / "data" / "clean"
    clean_dir.mkdir(parents=True)
    path = clean_dir / "panel.clean.csv"
    _clean_frame().to_csv(path, index=False)
    report = run_distribution(clean_dir, data_root=tmp_path / "data")
    assert report.opportunity_label == "Estimated distribution opportunity"
    assert report.manufacturer == "Unilever"
    assert report.current_period == "2026-08-16"
    assert report.sku_identity_field == "product"
    assert all(item.period == "2026-08-16" for item in report.opportunities)
    assert all("Reckitt" not in item.sku for item in report.opportunities)
    assert report.total_value_opportunity > 0
    assert report.total_volume_opportunity > 0
    assert report.report_output_path is not None
    assert Path(report.report_output_path).exists()
    wc = [item for item in report.opportunities if item.region == "Western Cape" and "Handy Andy" in item.sku]
    assert wc
    assert wc[0].benchmark_type != "historical_peak"
    assert "historical_peak_spike" in wc[0].outlier_flags
    zero = [item for item in report.opportunities if item.sku.startswith("Sunlight") and item.region == "Limpopo"]
    assert zero
    assert zero[0].current_stores == 0
    assert zero[0].store_gap >= 1
    assert zero[0].value_per_store > 0
    assert report.skipped_missing >= 1
    assert "Domestos" not in {item.sku for item in report.opportunities}


def test_agent_refuses_raw_inputs(tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    raw = raw_dir / "upload.csv"
    _clean_frame().to_csv(raw, index=False)
    with pytest.raises(DistributionLoadError, match="cleaned datasets"):
        run_distribution(raw, data_root=tmp_path / "data")


def test_missing_manufacturer_fails_closed(tmp_path: Path) -> None:
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    frame = _clean_frame()
    frame = frame[frame["manufacturer"] != "Unilever"]
    (clean_dir / "other.clean.csv").write_text(frame.to_csv(index=False), encoding="utf-8")
    with pytest.raises(DistributionLoadError, match="Unilever"):
        run_distribution(clean_dir, data_root=tmp_path)


def test_cli_help_mentions_clean_inputs() -> None:
    help_text = build_parser().format_help()
    assert "cleaned Unilever" in help_text
    assert "backend/data/clean" in help_text


def test_real_discovery_clean_file_if_present() -> None:
    clean_dir = Path("backend/data/clean")
    target = clean_dir / "New Discovery_2026-08-27 (3).clean.csv"
    if not target.exists():
        pytest.skip("Discovery cleaned extract is not in this checkout")
    report = run_distribution(clean_dir, write_outputs=False)
    assert report.source_clean_file.endswith("New Discovery_2026-08-27 (3).clean.csv")
    assert report.manufacturer == "Unilever"
    assert report.current_period == "2026-08-16"
    assert report.opportunity_label == "Estimated distribution opportunity"
    assert report.unilever_rows > 0
    assert all(item.period == report.current_period for item in report.top_opportunities)
