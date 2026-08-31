"""Load cleaned POS tables for the Distribution Agent. Never reads raw uploads."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from backend.agents.distribution.models import DistributionConfig

logger = logging.getLogger("backend.agents.distribution.loader")

REQUIRED_COLUMNS = (
    "date",
    "manufacturer",
    "retailer",
    "region",
    "sales_value",
    "sales_volume",
    "store_count",
)


class DistributionLoadError(ValueError):
    """Clean input cannot be used for distribution analysis."""


def _is_clean_file(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".clean.csv") or path.parent.name == "clean"


def _refuse_raw(path: Path) -> None:
    parts = {part.lower() for part in path.parts}
    if "raw" in parts and "clean" not in parts:
        raise DistributionLoadError(
            "Distribution Agent consumes only Data QA cleaned datasets, not files under data/raw/"
        )


def discover_clean_files(path: Path) -> list[Path]:
    path = path.expanduser().resolve()
    _refuse_raw(path)
    if path.is_dir():
        files = sorted(candidate for candidate in path.glob("*.clean.csv") if candidate.is_file())
        if not files:
            raise DistributionLoadError(f"No *.clean.csv files found in {path}")
        return files
    if not path.is_file():
        raise DistributionLoadError(f"Clean input does not exist: {path}")
    if not _is_clean_file(path):
        raise DistributionLoadError(
            f"{path} is not a cleaned dataset (expected *.clean.csv or a file inside data/clean/)"
        )
    return [path]


def manufacturer_mask(frame: pd.DataFrame, manufacturer: str) -> pd.Series:
    target = manufacturer.strip().casefold()
    series = frame["manufacturer"].astype("string").str.strip().str.casefold()
    return series.eq(target) | series.str.startswith(f"{target} ")


def _usable(frame: pd.DataFrame) -> bool:
    return all(column in frame.columns for column in REQUIRED_COLUMNS) and (
        "sku" in frame.columns or "product" in frame.columns
    )


def select_clean_file(files: list[Path], manufacturer: str) -> tuple[Path, pd.DataFrame]:
    """Pick the cleaned extract with the most usable Unilever (or configured manufacturer) rows."""
    ranked: list[tuple[int, Path, pd.DataFrame]] = []
    for file in files:
        frame = pd.read_csv(file)
        if not _usable(frame):
            logger.info("skip_clean_missing_columns path=%s columns=%s", file, list(frame.columns))
            continue
        count = int(manufacturer_mask(frame, manufacturer).sum())
        ranked.append((count, file, frame))
    usable = [item for item in ranked if item[0] > 0]
    if not usable:
        raise DistributionLoadError(
            f"No cleaned file among {[str(path) for path in files]} contains manufacturer={manufacturer} "
            "with date, retailer, region, store_count, sales value/volume, and product or sku"
        )
    usable.sort(key=lambda item: (-item[0], str(item[1])))
    count, chosen, frame = usable[0]
    logger.info("clean_source path=%s manufacturer_rows=%s", chosen, count)
    return chosen, frame


def attach_sku_identity(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Use sku when present; otherwise product is the SKU identity. Never hard-codes a SKU list."""
    result = frame.copy()
    if "sku" in result.columns and result["sku"].notna().any():
        if "product" in result.columns:
            result["sku"] = result["sku"].where(result["sku"].notna(), result["product"])
        return result, "sku"
    if "product" not in result.columns:
        raise DistributionLoadError("Cleaned data has neither sku nor product")
    result["sku"] = result["product"]
    return result, "product"


def load_manufacturer_clean(
    path: Path,
    config: DistributionConfig,
) -> tuple[Path, pd.DataFrame, str]:
    files = discover_clean_files(path)
    source, frame = select_clean_file(files, config.manufacturer)
    frame, identity = attach_sku_identity(frame)
    subset = frame.loc[manufacturer_mask(frame, config.manufacturer)].copy()
    subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
    subset["store_count"] = pd.to_numeric(subset["store_count"], errors="coerce")
    subset["sales_value"] = pd.to_numeric(subset["sales_value"], errors="coerce")
    subset["sales_volume"] = pd.to_numeric(subset["sales_volume"], errors="coerce")
    subset["sku"] = subset["sku"].astype("string").str.strip()
    subset["retailer"] = subset["retailer"].astype("string").str.strip()
    subset["region"] = subset["region"].astype("string").str.strip()
    logger.info(
        "manufacturer_loaded manufacturer=%s rows=%s identity=%s",
        config.manufacturer,
        len(subset),
        identity,
    )
    return source, subset, identity
