"""Load frozen specialist JSON reports and optional canonical commercial rows."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger("backend.agents.brain.loader")


class BrainLoadError(ValueError):
    """Commercial Brain inputs cannot be used."""


def _display(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def refuse_raw(path: Path) -> None:
    parts = {part.lower() for part in path.expanduser().resolve().parts}
    name = path.name.lower()
    if "raw" in parts and "data" in parts and "integrated" not in parts:
        raise BrainLoadError("Commercial Brain V1 does not read data/raw/ source files")
    if name.endswith(".clean.csv"):
        raise BrainLoadError("Commercial Brain V1 does not read Data QA *.clean.csv files directly")


def grain_key(product: str, retailer: str, region: str) -> str:
    return f"{product}|{retailer}|{region}"


@dataclass
class DistSignal:
    product: str
    retailer: str
    region: str
    value: float
    volume: float
    confidence: str
    current_stores: float | None
    benchmark_stores: float | None
    store_gap: float
    value_per_store: float | None
    volume_per_store: float | None
    outlier_flags: list[str] = field(default_factory=list)


@dataclass
class PriceSignal:
    product: str
    brand: str | None
    retailer: str
    region: str
    value: float
    volume: float
    confidence: str
    recommendation: str
    price_signal: str
    current_price: float | None
    benchmark_price: float | None
    distribution_primary_lever: bool
    mixed_promotion_comparison: bool
    outlier_flags: list[str] = field(default_factory=list)


@dataclass
class PromoSignal:
    product: str
    brand: str | None
    retailer: str
    region: str
    value: float
    volume: float
    confidence: str
    recommendation: str
    volume_uplift_pct: float | None
    distribution_primary_lever: bool
    subsidising_existing_demand: bool
    mixed_promotion_window: bool
    outlier_flags: list[str] = field(default_factory=list)


@dataclass
class CommercialRow:
    sales_value: float | None
    sales_volume: float | None
    store_count: float | None
    brand: str | None


@dataclass
class SpecialistBundle:
    stem: str
    distribution_path: Path
    price_path: Path
    promotion_path: Path
    commercial_path: Path | None
    dist: list[DistSignal]
    price: list[PriceSignal]
    promo: list[PromoSignal]
    commercial: dict[str, CommercialRow]
    current_period: str
    distribution_limitations: list[str]
    price_limitations: list[str]
    promotion_limitations: list[str]


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrainLoadError(f"Cannot read specialist report {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BrainLoadError(f"Specialist report {path} is not a JSON object")
    return payload


def _opportunities(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("opportunities")
    if not isinstance(raw, list) or not raw:
        raw = (
            payload.get("top_opportunities")
            or payload.get("top_price_opportunities")
            or payload.get("top_promotional_opportunities")
            or []
        )
    return [item for item in raw if isinstance(item, dict)]


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _parse_dist(payload: dict[str, object]) -> list[DistSignal]:
    out: list[DistSignal] = []
    for row in _opportunities(payload):
        product = str(row.get("sku") or row.get("product") or "").strip()
        retailer = str(row.get("retailer") or "").strip()
        region = str(row.get("region") or "").strip()
        if not product or not retailer or not region:
            continue
        value = _num(row.get("value_opportunity"))
        volume = _num(row.get("volume_opportunity"))
        if value is None or volume is None:
            continue
        flags = row.get("outlier_flags") or []
        out.append(
            DistSignal(
                product=product,
                retailer=retailer,
                region=region,
                value=value,
                volume=volume,
                confidence=str(row.get("confidence") or "LOW"),
                current_stores=_num(row.get("current_stores")),
                benchmark_stores=_num(row.get("benchmark_stores")),
                store_gap=float(_num(row.get("store_gap")) or 0.0),
                value_per_store=_num(row.get("value_per_store")),
                volume_per_store=_num(row.get("volume_per_store")),
                outlier_flags=[str(item) for item in flags] if isinstance(flags, list) else [],
            )
        )
    return out


def _parse_price(payload: dict[str, object]) -> list[PriceSignal]:
    out: list[PriceSignal] = []
    for row in _opportunities(payload):
        product = str(row.get("product") or row.get("sku") or "").strip()
        retailer = str(row.get("retailer") or "").strip()
        region = str(row.get("region") or "").strip()
        if not product or not retailer or not region:
            continue
        value = _num(row.get("estimated_value_opportunity"))
        volume = _num(row.get("estimated_volume_opportunity"))
        if value is None or volume is None:
            continue
        brand = row.get("brand")
        flags = row.get("outlier_flags") or []
        out.append(
            PriceSignal(
                product=product,
                brand=None if brand in {None, ""} else str(brand),
                retailer=retailer,
                region=region,
                value=value,
                volume=volume,
                confidence=str(row.get("confidence") or "LOW"),
                recommendation=str(row.get("recommendation") or ""),
                price_signal=str(row.get("price_signal") or ""),
                current_price=_num(row.get("current_price")),
                benchmark_price=_num(row.get("benchmark_price")),
                distribution_primary_lever=bool(row.get("distribution_primary_lever")),
                mixed_promotion_comparison=bool(row.get("mixed_promotion_comparison")),
                outlier_flags=[str(item) for item in flags] if isinstance(flags, list) else [],
            )
        )
    return out


def _parse_promo(payload: dict[str, object]) -> list[PromoSignal]:
    out: list[PromoSignal] = []
    for row in _opportunities(payload):
        product = str(row.get("product") or row.get("sku") or "").strip()
        retailer = str(row.get("retailer") or "").strip()
        region = str(row.get("region") or "").strip()
        if not product or not retailer or not region:
            continue
        value = _num(row.get("estimated_incremental_value"))
        volume = _num(row.get("estimated_incremental_volume"))
        if value is None or volume is None:
            continue
        brand = row.get("brand")
        flags = row.get("outlier_flags") or []
        out.append(
            PromoSignal(
                product=product,
                brand=None if brand in {None, ""} else str(brand),
                retailer=retailer,
                region=region,
                value=value,
                volume=volume,
                confidence=str(row.get("confidence") or "LOW"),
                recommendation=str(row.get("recommendation") or ""),
                volume_uplift_pct=_num(row.get("volume_uplift_pct")),
                distribution_primary_lever=bool(row.get("distribution_primary_lever")),
                subsidising_existing_demand=bool(row.get("subsidising_existing_demand")),
                mixed_promotion_window=bool(row.get("mixed_promotion_window")),
                outlier_flags=[str(item) for item in flags] if isinstance(flags, list) else [],
            )
        )
    return out


def _load_commercial(path: Path) -> dict[str, CommercialRow]:
    frame = pd.read_csv(path, low_memory=False)
    if "date" not in frame.columns:
        return {}
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if "manufacturer" in frame.columns:
        maker = frame["manufacturer"].astype("string").str.strip().str.casefold()
        frame = frame.loc[maker == "unilever"]
    if "in_pos" in frame.columns:
        text = frame["in_pos"].astype("string").str.strip().str.casefold()
        frame = frame.loc[text.isin(["true", "1"])]
    if frame.empty or frame["date"].dropna().empty:
        return {}
    current = frame["date"].max()
    subset = frame.loc[frame["date"] == current]
    rows: dict[str, CommercialRow] = {}
    for rec in subset.to_dict(orient="records"):
        product = str(rec.get("product") or "").strip()
        retailer = str(rec.get("retailer") or "").strip()
        region = str(rec.get("region") or "").strip()
        if not product or not retailer or not region:
            continue
        brand = rec.get("brand")
        rows[grain_key(product, retailer, region)] = CommercialRow(
            sales_value=_num(rec.get("sales_value")),
            sales_volume=_num(rec.get("sales_volume")),
            store_count=_num(rec.get("store_count")),
            brand=None if brand in {None, ""} or (isinstance(brand, float) and brand != brand) else str(brand),
        )
    return rows


def _stem_from(path: Path, suffix: str) -> str:
    name = path.name
    if name.endswith(suffix):
        return name[: -len(suffix)]
    return path.stem


def discover_bundle(path: Path) -> SpecialistBundle:
    path = path.expanduser().resolve()
    refuse_raw(path)
    if path.is_file() and path.name.endswith(".brain.json"):
        raise BrainLoadError("Pass a data root or specialist report directory, not a Brain output file")

    data_root = path
    if path.is_file():
        data_root = path.parent.parent if path.parent.name.endswith("_reports") or path.parent.name in {
            "distribution_reports",
            "price_reports",
            "promotion_reports",
            "integrated",
        } else path.parent
    if data_root.name in {"distribution_reports", "price_reports", "promotion_reports", "integrated"}:
        data_root = data_root.parent

    dist_dir = data_root / "distribution_reports"
    price_dir = data_root / "price_reports"
    promo_dir = data_root / "promotion_reports"
    integrated_dir = data_root / "integrated"
    dist_files = sorted(dist_dir.glob("*.distribution.json")) if dist_dir.is_dir() else []
    price_iter = price_dir.glob("*.price.json") if price_dir.is_dir() else []
    promo_iter = promo_dir.glob("*.promotion.json") if promo_dir.is_dir() else []
    price_files = {_stem_from(item, ".price.json"): item for item in price_iter}
    promo_files = {_stem_from(item, ".promotion.json"): item for item in promo_iter}
    commercial_files = {
        item.name.removesuffix(".commercial.csv"): item
        for item in (integrated_dir.glob("*.commercial.csv") if integrated_dir.is_dir() else [])
    }
    matched: list[tuple[str, Path, Path, Path]] = []
    for dist_path in dist_files:
        stem = _stem_from(dist_path, ".distribution.json")
        if stem in price_files and stem in promo_files:
            matched.append((stem, dist_path, price_files[stem], promo_files[stem]))
    if not matched:
        raise BrainLoadError(
            f"No matching Distribution + Price + Promotion reports under {data_root} "
            "(expected *.distribution.json, *.price.json, *.promotion.json with the same stem)"
        )
    matched.sort(key=lambda item: (0 if "Discovery" in item[0] else 1, -item[1].stat().st_mtime, item[0]))
    stem, dist_path, price_path, promo_path = matched[0]
    dist_payload = _read_json(dist_path)
    price_payload = _read_json(price_path)
    promo_payload = _read_json(promo_path)
    commercial_path = commercial_files.get(stem)
    commercial: dict[str, CommercialRow] = {}
    if commercial_path is not None:
        commercial = _load_commercial(commercial_path)
    period = str(
        price_payload.get("current_period")
        or promo_payload.get("current_period")
        or dist_payload.get("current_period")
        or ""
    )
    logger.info(
        "brain_inputs dist=%s price=%s promo=%s commercial=%s",
        dist_path,
        price_path,
        promo_path,
        commercial_path,
    )
    return SpecialistBundle(
        stem=stem,
        distribution_path=dist_path,
        price_path=price_path,
        promotion_path=promo_path,
        commercial_path=commercial_path,
        dist=_parse_dist(dist_payload),
        price=_parse_price(price_payload),
        promo=_parse_promo(promo_payload),
        commercial=commercial,
        current_period=period,
        distribution_limitations=[str(item) for item in (dist_payload.get("limitations") or []) if item],
        price_limitations=[str(item) for item in (price_payload.get("limitations") or []) if item],
        promotion_limitations=[str(item) for item in (promo_payload.get("limitations") or []) if item],
    )
