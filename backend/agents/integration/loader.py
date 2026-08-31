"""Load cleaned POS and the committed Unilever price/promotion extract.

Never reads Data QA raw POS uploads as the POS source. Never writes back to either source file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from backend.agents.integration.models import JOIN_KEY, IntegrationConfig

logger = logging.getLogger("backend.agents.integration.loader")


class IntegrationLoadError(ValueError):
    """A source file cannot be used for commercial integration."""


def _display(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def refuse_raw_pos(path: Path) -> None:
    parts = {part.lower() for part in path.expanduser().resolve().parts}
    if "raw" in parts and "clean" not in parts:
        raise IntegrationLoadError(
            "Integration POS source must be a Data QA cleaned dataset, not a file under data/raw/"
        )


def resolve_pos_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    refuse_raw_pos(path)
    if path.is_dir():
        files = sorted(candidate for candidate in path.glob("*.clean.csv") if candidate.is_file())
        if not files:
            raise IntegrationLoadError(f"No *.clean.csv files found in {path}")
        preferred = [item for item in files if "New Discovery" in item.name]
        chosen = preferred[0] if preferred else files[0]
        return chosen
    if not path.is_file():
        raise IntegrationLoadError(f"POS input does not exist: {path}")
    name = path.name.lower()
    if not (name.endswith(".clean.csv") or path.parent.name == "clean"):
        raise IntegrationLoadError(
            f"{path} is not a cleaned POS dataset (expected *.clean.csv or a file inside data/clean/)"
        )
    return path


def resolve_price_promo_path(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    if path.is_dir():
        matches = sorted(path.glob("Unilever_Price_Promo*.csv")) + sorted(path.glob("*Price*Promo*.csv"))
        files = [item for item in matches if item.is_file()]
        if not files:
            raise IntegrationLoadError(f"No Unilever price/promotion CSV found in {path}")
        return files[0]
    if not path.is_file():
        raise IntegrationLoadError(f"Price/promotion input does not exist: {path}")
    return path


def _require_columns(frame: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise IntegrationLoadError(f"{label} is missing required columns: {missing}")


def _norm_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def load_pos(path: Path, config: IntegrationConfig) -> pd.DataFrame:
    path = resolve_pos_path(path)
    frame = pd.read_csv(path)
    cols = config.pos_columns
    required = [cols["product"], cols["retailer"], cols["region"], cols["date"]]
    _require_columns(frame, required, f"POS {_display(path)}")
    out = pd.DataFrame()
    out["product"] = _norm_text(frame[cols["product"]])
    out["manufacturer"] = _norm_text(frame[cols["manufacturer"]]) if cols["manufacturer"] in frame.columns else pd.NA
    if cols.get("brand") and cols["brand"] in frame.columns:
        out["brand"] = _norm_text(frame[cols["brand"]])
    else:
        out["brand"] = pd.Series(pd.NA, index=frame.index, dtype="string")
    out["retailer"] = _norm_text(frame[cols["retailer"]])
    out["region"] = _norm_text(frame[cols["region"]])
    out["date"] = pd.to_datetime(frame[cols["date"]], errors="coerce").dt.normalize()
    for dest, src in (
        ("sales_value", "sales_value"),
        ("sales_volume", "sales_volume"),
        ("store_count", "store_count"),
        ("pos_current_price", "current_price"),
        ("pos_percent_time_on_promo", "percent_time_on_promo"),
        ("pos_percent_sales_on_promo", "percent_sales_on_promo"),
    ):
        column = cols[src]
        if column in frame.columns:
            out[dest] = pd.to_numeric(frame[column], errors="coerce")
        else:
            out[dest] = pd.Series(pd.NA, index=frame.index, dtype="Float64")
    source_col = cols.get("source_row", "_source_row")
    if source_col in frame.columns:
        out["pos_source_row"] = pd.to_numeric(frame[source_col], errors="coerce")
    else:
        out["pos_source_row"] = pd.Series(pd.NA, index=frame.index, dtype="Float64")
    missing_key = out["product"].isna() | out["retailer"].isna() | out["region"].isna() | out["date"].isna()
    if bool(missing_key.any()):
        raise IntegrationLoadError(
            f"POS {_display(path)} has {int(missing_key.sum())} rows with a missing join-key field"
        )
    duplicated = out.duplicated(list(JOIN_KEY), keep=False)
    if bool(duplicated.any()):
        raise IntegrationLoadError(
            f"POS {_display(path)} is not unique on {list(JOIN_KEY)} "
            f"({int(duplicated.sum())} rows in duplicate groups). Refusing to collapse POS grains."
        )
    logger.info("pos_loaded path=%s rows=%s", _display(path), len(out))
    return out


def load_price_promo(path: Path, config: IntegrationConfig) -> pd.DataFrame:
    path = resolve_price_promo_path(path)
    frame = pd.read_csv(path)
    cols = config.promo_columns
    required = [
        cols["product"],
        cols["retailer"],
        cols["region"],
        config.promo_date_column,
        config.promotion_indicator_column,
    ]
    _require_columns(frame, required, f"price/promo {_display(path)}")
    out = pd.DataFrame()
    out["product"] = _norm_text(frame[cols["product"]])
    out["manufacturer"] = _norm_text(frame[cols["manufacturer"]]) if cols["manufacturer"] in frame.columns else pd.NA
    out["brand"] = _norm_text(frame[cols["brand"]]) if cols["brand"] in frame.columns else pd.NA
    out["retailer"] = _norm_text(frame[cols["retailer"]])
    out["region"] = _norm_text(frame[cols["region"]])
    out["date"] = pd.to_datetime(
        frame[config.promo_date_column],
        format=config.promo_date_format,
        errors="coerce",
    ).dt.normalize()
    out["promotion_indicator"] = pd.to_numeric(frame[config.promotion_indicator_column], errors="coerce")
    pid_col = cols.get("productsid")
    if pid_col and pid_col in frame.columns:
        out["productsid"] = frame[pid_col].astype("Int64").astype("string")
    else:
        out["productsid"] = pd.Series(pd.NA, index=frame.index, dtype="string")
    for dest, src in (
        ("ave_price_quantity", "ave_price_quantity"),
        ("rsp_on_promo", "rsp_on_promo"),
        ("sales_on_promo", "sales_on_promo"),
        ("time_on_promo", "time_on_promo"),
        ("sales_pct_on_promo", "sales_pct_on_promo"),
    ):
        column = cols[src]
        if column in frame.columns:
            out[dest] = pd.to_numeric(frame[column], errors="coerce")
        else:
            out[dest] = pd.Series(pd.NA, index=frame.index, dtype="Float64")
    missing_key = out["product"].isna() | out["retailer"].isna() | out["region"].isna() | out["date"].isna()
    dropped = int(missing_key.sum())
    if dropped:
        logger.warning("price_promo_dropped_missing_join_key rows=%s", dropped)
        out = out.loc[~missing_key].copy()
    logger.info("price_promo_loaded path=%s rows=%s", _display(path), len(out))
    return out
