"""Orchestrate POS load → promo pivot → outer join → flags → canonical write."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from backend.agents.integration.flags import attach_flags
from backend.agents.integration.join import outer_join
from backend.agents.integration.loader import (
    load_pos,
    load_price_promo,
    resolve_pos_path,
    resolve_price_promo_path,
)
from backend.agents.integration.models import (
    FIELD_SOURCES,
    JOIN_KEY,
    IntegrationReport,
    IntegrationStatus,
    ProductMappingIssues,
    WeeklyCoverage,
    load_integration_config,
)
from backend.agents.integration.pivot import pivot_promotion_indicator

logger = logging.getLogger("backend.agents.integration")

CANONICAL_COLUMNS = [
    "product",
    "manufacturer",
    "brand",
    "retailer",
    "region",
    "date",
    "sales_value",
    "sales_volume",
    "store_count",
    "pos_current_price",
    "off_promo_price",
    "on_promo_price",
    "off_promo_rsp",
    "on_promo_rsp",
    "off_promo_sales",
    "on_promo_sales",
    "off_promo_time",
    "on_promo_time",
    "off_promo_sales_pct",
    "on_promo_sales_pct",
    "pos_percent_time_on_promo",
    "pos_percent_sales_on_promo",
    "promotion_indicator_off_present",
    "promotion_indicator_on_present",
    "promotion_states",
    "productsid",
    "productsid_count",
    "price_promo_source_rows",
    "pos_source_row",
    "in_pos",
    "in_price_promo",
    "price_promo_available",
    "price_enabled",
    "promotion_enabled",
    "flag_unmatched_pos",
    "flag_unmatched_price_promo",
    "flag_multiple_source_matches",
    "flag_missing_price",
    "flag_missing_promotion_metrics",
    "flag_missing_rsp",
    "flag_price_promo_unavailable_for_period",
    "flag_ambiguous_product_mapping",
]

BOOL_COLUMNS = [
    "promotion_indicator_off_present",
    "promotion_indicator_on_present",
    "in_pos",
    "in_price_promo",
    "price_promo_available",
    "price_enabled",
    "promotion_enabled",
    "flag_unmatched_pos",
    "flag_unmatched_price_promo",
    "flag_multiple_source_matches",
    "flag_missing_price",
    "flag_missing_promotion_metrics",
    "flag_missing_rsp",
    "flag_price_promo_unavailable_for_period",
    "flag_ambiguous_product_mapping",
]


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return str(resolved)


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _grain_key(frame: pd.DataFrame) -> pd.Series:
    dates = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    return (
        frame["product"].astype("string")
        + "|"
        + frame["retailer"].astype("string")
        + "|"
        + frame["region"].astype("string")
        + "|"
        + dates.astype("string")
    )


def _date_label(value: object) -> str:
    stamp = pd.Timestamp(value)
    return stamp.strftime("%Y-%m-%d")


def _match_rate(matched: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(100.0 * matched / total, 4)


def _unilever_mask(frame: pd.DataFrame) -> pd.Series:
    series = frame["manufacturer"].astype("string").str.strip().str.casefold()
    return series.eq("unilever") | series.str.startswith("unilever ")


def _product_mapping(pos: pd.DataFrame, promo: pd.DataFrame, canonical: pd.DataFrame) -> ProductMappingIssues:
    id_to_name = promo.dropna(subset=["productsid"]).groupby("productsid")["product"].nunique()
    name_to_id = promo.dropna(subset=["productsid"]).groupby("product")["productsid"].nunique()
    multi_names = sorted(name_to_id[name_to_id.gt(1)].index.astype(str).tolist())
    pos_names = set(pos["product"].dropna().astype(str))
    promo_names = set(promo["product"].dropna().astype(str))
    pos_only = sorted(pos_names - promo_names)
    if "flag_ambiguous_product_mapping" in canonical.columns:
        multi_grains = int(canonical["flag_ambiguous_product_mapping"].fillna(False).sum())
    else:
        multi_grains = 0
    return ProductMappingIssues(
        productsid_to_one_product=int((id_to_name.gt(1)).sum()) == 0,
        ids_with_multiple_product_names=int((id_to_name.gt(1)).sum()),
        products_with_multiple_ids=int((name_to_id.gt(1)).sum()),
        products_with_multiple_ids_names=multi_names,
        pos_products_absent_from_price_promo=pos_only,
        canonical_grains_with_multiple_ids=multi_grains,
    )


def _weekly_coverage(pos: pd.DataFrame, promo: pd.DataFrame, promo_wide: pd.DataFrame) -> list[WeeklyCoverage]:
    pos_keys = set(_grain_key(pos))
    promo_keys = set(_grain_key(promo_wide))
    matched_keys = pos_keys & promo_keys
    pos = pos.copy()
    promo = promo.copy()
    pos["_date"] = pd.to_datetime(pos["date"]).dt.strftime("%Y-%m-%d")
    promo["_date"] = pd.to_datetime(promo["date"]).dt.strftime("%Y-%m-%d")
    pos["_k"] = _grain_key(pos)
    promo["_k"] = _grain_key(promo)
    dates = sorted(set(pos["_date"]).union(set(promo["_date"])))
    rows: list[WeeklyCoverage] = []
    for date in dates:
        pos_week = pos.loc[pos["_date"].eq(date)]
        promo_week = promo.loc[promo["_date"].eq(date)]
        pos_n = len(pos_week)
        promo_n = len(promo_week)
        matched = int(pos_week["_k"].isin(matched_keys).sum())
        unmatched_pos = pos_n - matched
        unmatched_promo = int((~promo_week["_k"].isin(pos_keys)).sum())
        rows.append(
            WeeklyCoverage(
                date=date,
                pos_records=pos_n,
                price_promo_records=promo_n,
                matched=matched,
                unmatched_pos=unmatched_pos,
                unmatched_price_promo=unmatched_promo,
                match_pct=_match_rate(matched, pos_n),
            )
        )
    return rows


def _limitations(
    *,
    overlapping: list[str],
    non_overlapping: list[str],
    mapping: ProductMappingIssues,
    unmatched_pos: int,
    unmatched_promo_grains: int,
    multiple_source: int,
    canonical_duplicates: int,
) -> list[str]:
    notes: list[str] = []
    if canonical_duplicates:
        notes.append(f"Canonical grain is not unique ({canonical_duplicates} extra rows).")
    notes.append("Join key is Product + Retailer + Region + Date. ProductsID is lineage only.")
    notes.append(
        "Promotion Indicator 0/1 is pivoted into off_promo_* / on_promo_* columns; "
        "two source rows per grain are a promotion state, not a duplicate."
    )
    notes.append(
        "4 Weeks CY Ave RSP On Promo is stored as off_promo_rsp / on_promo_rsp and is not renamed to normal price."
    )
    notes.append("Missing price and promotion metrics are preserved as missing; they are not converted to zero.")
    if non_overlapping:
        notes.append(
            "POS weeks with no price/promotion source remain in the canonical table: " + ", ".join(non_overlapping)
        )
    if len(overlapping) < 12:
        notes.append(
            f"Price/promotion calendar has {len(overlapping)} overlapping week(s); not a 12-week price/promo panel."
        )
    if unmatched_pos:
        notes.append(f"{unmatched_pos} POS records have no price/promotion grain (not forced to match).")
    if unmatched_promo_grains:
        notes.append(
            f"{unmatched_promo_grains} price/promotion grains have no POS row "
            "(broader Unilever house and extra banners)."
        )
    if mapping.products_with_multiple_ids:
        notes.append(
            f"{mapping.products_with_multiple_ids} product names map to multiple ProductsID values."
        )
    if mapping.pos_products_absent_from_price_promo:
        notes.append(
            f"{len(mapping.pos_products_absent_from_price_promo)} POS product names "
            "are absent from the price/promo extract."
        )
    if multiple_source:
        notes.append(
            f"{multiple_source} canonical grains collapsed multiple ProductsID rows per indicator; "
            "conflicting metrics are left missing."
        )
    notes.append("Price Agent, Promotion Agent, and Commercial Brain are not built in this sprint.")
    return notes


def _status(
    *,
    canonical_duplicates: int,
    unmatched_pos: int,
    unmatched_promo_grains: int,
    overlapping: list[str],
    non_overlapping: list[str],
    mapping: ProductMappingIssues,
    multiple_source: int,
) -> IntegrationStatus:
    if canonical_duplicates:
        return IntegrationStatus.NOT_READY
    warnings = bool(
        unmatched_pos
        or unmatched_promo_grains
        or non_overlapping
        or len(overlapping) < 12
        or mapping.products_with_multiple_ids
        or mapping.pos_products_absent_from_price_promo
        or mapping.ids_with_multiple_product_names
        or multiple_source
    )
    if warnings:
        return IntegrationStatus.READY_WITH_WARNINGS
    return IntegrationStatus.READY


def _order_columns(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = [column for column in CANONICAL_COLUMNS if column in frame.columns]
    extras = [column for column in frame.columns if column not in ordered and column != "unexpected_indicator_rows"]
    return frame[ordered + extras]


def _stringify_bools(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in BOOL_COLUMNS:
        if column not in out.columns:
            continue
        mapped = pd.Series(pd.NA, index=out.index, dtype="string")
        mapped = mapped.mask(out[column].eq(True), "true")
        mapped = mapped.mask(out[column].eq(False), "false")
        out[column] = mapped
    return out


def write_canonical_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    export = _order_columns(frame)
    export = export.copy()
    export["date"] = pd.to_datetime(export["date"]).dt.strftime("%Y-%m-%d")
    export = _stringify_bools(export)
    export.to_csv(path, index=False, na_rep="")


def _default_data_root(pos_path: Path) -> Path:
    resolved = pos_path.expanduser().resolve()
    if resolved.parent.name == "clean":
        return resolved.parent.parent
    return Path("backend/data").resolve()


def run_integration(
    pos_input: Path | None = None,
    price_promo_input: Path | None = None,
    *,
    data_root: Path | None = None,
    config_path: Path | None = None,
    write_outputs: bool = True,
) -> tuple[pd.DataFrame, IntegrationReport]:
    _configure_logging()
    config = load_integration_config(config_path)
    pos_path = resolve_pos_path(Path(pos_input) if pos_input is not None else Path(config.default_pos_path))
    promo_path = resolve_price_promo_path(
        Path(price_promo_input) if price_promo_input is not None else Path(config.default_price_promo_path)
    )
    pos = load_pos(pos_path, config)
    promo = load_price_promo(promo_path, config)
    promo_wide = pivot_promotion_indicator(promo, config)
    canonical = outer_join(pos, promo_wide)
    promo_dates = set(pd.to_datetime(promo["date"]).dropna().dt.normalize().unique())
    canonical = attach_flags(canonical, promo_dates)
    canonical = _order_columns(canonical)

    grain_dups = int(canonical.duplicated(list(JOIN_KEY), keep="first").sum())
    pos_dates = set(pd.to_datetime(pos["date"]).dropna().dt.strftime("%Y-%m-%d"))
    promo_date_labels = {_date_label(item) for item in promo_dates}
    overlapping = sorted(pos_dates & promo_date_labels)
    non_overlapping = sorted(pos_dates.symmetric_difference(promo_date_labels))

    pos_keys = set(_grain_key(pos))
    promo_keys = set(_grain_key(promo_wide))
    matched_keys = pos_keys & promo_keys
    matched_pos = int(_grain_key(pos).isin(matched_keys).sum())
    unmatched_pos = len(pos) - matched_pos
    unmatched_promo_grains = len(promo_keys - pos_keys)
    unmatched_promo_rows = int((~_grain_key(promo).isin(pos_keys)).sum())

    unilever_pos = pos.loc[_unilever_mask(pos)]
    unilever_matched = int(_grain_key(unilever_pos).isin(matched_keys).sum()) if len(unilever_pos) else 0
    overlap_mask = pd.to_datetime(unilever_pos["date"]).dt.strftime("%Y-%m-%d").isin(overlapping)
    unilever_overlap = unilever_pos.loc[overlap_mask]
    unilever_overlap_matched = (
        int(_grain_key(unilever_overlap).isin(matched_keys).sum()) if len(unilever_overlap) else 0
    )

    multi_state = int(
        (
            promo_wide["promotion_indicator_off_present"].fillna(False)
            & promo_wide["promotion_indicator_on_present"].fillna(False)
        ).sum()
    )
    multiple_source = int(canonical["flag_multiple_source_matches"].fillna(False).sum())
    mapping = _product_mapping(pos, promo, canonical)
    july_26 = int(
        (
            canonical["in_pos"].fillna(False)
            & pd.to_datetime(canonical["date"]).dt.strftime("%Y-%m-%d").eq("2026-07-26")
        ).sum()
    )

    status = _status(
        canonical_duplicates=grain_dups,
        unmatched_pos=unmatched_pos,
        unmatched_promo_grains=unmatched_promo_grains,
        overlapping=overlapping,
        non_overlapping=non_overlapping,
        mapping=mapping,
        multiple_source=multiple_source,
    )
    limitations = _limitations(
        overlapping=overlapping,
        non_overlapping=non_overlapping,
        mapping=mapping,
        unmatched_pos=unmatched_pos,
        unmatched_promo_grains=unmatched_promo_grains,
        multiple_source=multiple_source,
        canonical_duplicates=grain_dups,
    )

    root = data_root.expanduser().resolve() if data_root is not None else _default_data_root(pos_path)
    stem = pos_path.name.removesuffix(".clean.csv").removesuffix(".csv")
    canonical_path: Path | None = None
    report_path: Path | None = None
    if write_outputs:
        canonical_path = root / "integrated" / f"{stem}.commercial.csv"
        report_path = root / "integration_reports" / f"{stem}.integration.json"
        write_canonical_csv(canonical, canonical_path)

    report = IntegrationReport(
        status=status,
        grain=list(JOIN_KEY),
        join_key=list(JOIN_KEY),
        pos_source_file=_display_path(pos_path),
        price_promo_source_file=_display_path(promo_path),
        canonical_output_path=_display_path(canonical_path) if canonical_path else None,
        report_output_path=_display_path(report_path) if report_path else None,
        pos_row_count=len(pos),
        price_promo_row_count=len(promo),
        price_promo_grain_count=len(promo_wide),
        canonical_row_count=len(canonical),
        overlapping_weeks=overlapping,
        non_overlapping_weeks=non_overlapping,
        match_rate_pos=_match_rate(matched_pos, len(pos)),
        match_rate_unilever_pos=_match_rate(unilever_matched, len(unilever_pos)),
        match_rate_unilever_overlapping_weeks=_match_rate(unilever_overlap_matched, len(unilever_overlap)),
        unmatched_pos_records=unmatched_pos,
        unmatched_price_promo_records=unmatched_promo_rows,
        unmatched_price_promo_grains=unmatched_promo_grains,
        matched_pos_records=matched_pos,
        promotion_multi_state_grains=multi_state,
        multiple_source_match_grains=multiple_source,
        canonical_duplicate_rows=grain_dups,
        price_enabled_rows=int(canonical["price_enabled"].fillna(False).sum()),
        promotion_enabled_rows=int(canonical["promotion_enabled"].fillna(False).sum()),
        price_promo_available_rows=int(canonical["price_promo_available"].fillna(False).sum()),
        july_26_pos_rows_retained=july_26,
        product_mapping=mapping,
        weekly=_weekly_coverage(pos, promo, promo_wide),
        field_sources=dict(FIELD_SOURCES),
        limitations=limitations,
    )
    if write_outputs and report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n", encoding="utf-8")
        logger.info("canonical_written path=%s rows=%s", canonical_path, len(canonical))
        logger.info("report_written path=%s status=%s", report_path, report.status)
    return canonical, report
