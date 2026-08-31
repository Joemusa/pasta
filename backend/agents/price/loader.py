"""Load the canonical integrated commercial table. Never reads raw or Data QA clean extracts."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from backend.agents.price.models import PriceConfig

logger = logging.getLogger("backend.agents.price.loader")

REQUIRED_COLUMNS = (
    "product",
    "retailer",
    "region",
    "date",
    "sales_value",
    "sales_volume",
    "store_count",
    "pos_current_price",
)


class PriceLoadError(ValueError):
    """Canonical input cannot be used for the Price Agent."""


def _display(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def refuse_non_integrated(path: Path) -> None:
    parts = {part.lower() for part in path.expanduser().resolve().parts}
    name = path.name.lower()
    if "raw" in parts and "integrated" not in parts:
        raise PriceLoadError("Price Agent V1 consumes only the canonical integrated dataset, not data/raw/")
    if name.endswith(".clean.csv"):
        raise PriceLoadError(
            "Price Agent V1 consumes the canonical integrated commercial CSV, not Data QA *.clean.csv files"
        )


def discover_integrated_files(path: Path) -> list[Path]:
    path = path.expanduser().resolve()
    refuse_non_integrated(path)
    if path.is_dir():
        files = sorted(candidate for candidate in path.glob("*.commercial.csv") if candidate.is_file())
        if not files:
            raise PriceLoadError(f"No *.commercial.csv files found in {path}")
        return files
    if not path.is_file():
        raise PriceLoadError(f"Integrated input does not exist: {path}")
    if not path.name.lower().endswith(".commercial.csv") and path.parent.name != "integrated":
        raise PriceLoadError(
            f"{path} is not a canonical integrated dataset (expected *.commercial.csv or a file in data/integrated/)"
        )
    return [path]


def _parse_bool(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip().str.casefold()
    out = pd.Series(pd.NA, index=series.index, dtype="boolean")
    out = out.mask(text.eq("true"), True)
    out = out.mask(text.eq("false"), False)
    numeric = pd.to_numeric(series, errors="coerce")
    out = out.mask(numeric.eq(1), True)
    out = out.mask(numeric.eq(0), False)
    return out


def manufacturer_mask(frame: pd.DataFrame, manufacturer: str) -> pd.Series:
    target = manufacturer.strip().casefold()
    series = frame["manufacturer"].astype("string").str.strip().str.casefold()
    return series.eq(target) | series.str.startswith(f"{target} ")


def _usable(frame: pd.DataFrame) -> bool:
    return all(column in frame.columns for column in REQUIRED_COLUMNS)


def select_integrated_file(files: list[Path], manufacturer: str) -> tuple[Path, pd.DataFrame]:
    ranked: list[tuple[int, Path, pd.DataFrame]] = []
    for file in files:
        frame = pd.read_csv(file, low_memory=False)
        if not _usable(frame):
            logger.info("skip_integrated_missing_columns path=%s", file)
            continue
        if "in_pos" in frame.columns:
            in_pos = _parse_bool(frame["in_pos"]).fillna(False)
        else:
            in_pos = pd.Series(True, index=frame.index)
        count = int((manufacturer_mask(frame, manufacturer) & in_pos).sum())
        ranked.append((count, file, frame))
    usable = [item for item in ranked if item[0] > 0]
    if not usable:
        raise PriceLoadError(
            f"No integrated file among {[str(path) for path in files]} contains manufacturer={manufacturer} "
            "with product, retailer, region, date, sales, stores, and pos_current_price"
        )
    usable.sort(key=lambda item: (-item[0], str(item[1])))
    count, chosen, frame = usable[0]
    logger.info("integrated_source path=%s manufacturer_pos_rows=%s", chosen, count)
    return chosen, frame


def load_integrated_unilever(path: Path, config: PriceConfig) -> tuple[Path, pd.DataFrame]:
    files = discover_integrated_files(path)
    source, frame = select_integrated_file(files, config.manufacturer)
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    for column in ("product", "retailer", "region", "manufacturer", "brand"):
        if column in work.columns:
            work[column] = work[column].astype("string").str.strip()
        elif column == "brand":
            work[column] = pd.Series(pd.NA, index=work.index, dtype="string")
    for column in (
        "sales_value",
        "sales_volume",
        "store_count",
        "pos_current_price",
        "pos_percent_time_on_promo",
        "pos_percent_sales_on_promo",
        "off_promo_time",
        "on_promo_time",
        "off_promo_sales_pct",
        "on_promo_sales_pct",
        "off_promo_price",
        "on_promo_price",
        "off_promo_rsp",
        "on_promo_rsp",
    ):
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
        else:
            work[column] = pd.Series(pd.NA, index=work.index, dtype="Float64")
    for column in ("in_pos", "flag_ambiguous_product_mapping", "flag_missing_promotion_metrics"):
        if column in work.columns:
            work[column] = _parse_bool(work[column])
        else:
            work[column] = pd.Series(False, index=work.index, dtype="boolean")
    mask = manufacturer_mask(work, config.manufacturer) & work["in_pos"].fillna(False)
    subset = work.loc[mask].copy()
    logger.info("price_loaded manufacturer=%s in_pos_rows=%s", config.manufacturer, len(subset))
    return source, subset
