"""Pivot Promotion Indicator 0/1 into off-promo / on-promo columns.

Multiple rows per Product x Retailer x Region x Date that differ only by
Promotion Indicator are a promotion state, not a duplicate grain.

Multiple ProductsID values at the same grain are flagged; conflicting metrics
are left missing rather than averaged or picked arbitrarily.
"""

from __future__ import annotations

import pandas as pd

from backend.agents.integration.models import JOIN_KEY, IntegrationConfig

FLOAT_COLUMNS = (
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
)


def _unique_or_na(series: pd.Series) -> object:
    values = pd.unique(series.dropna())
    if len(values) == 0:
        return pd.NA
    if len(values) == 1:
        return values[0]
    return pd.NA


def _join_ids(series: pd.Series) -> object:
    values = sorted({str(item) for item in series.dropna().tolist() if str(item) != "<NA>"})
    if not values:
        return pd.NA
    return "|".join(values)


def _aggregate_indicator_slice(frame: pd.DataFrame, side: str) -> pd.DataFrame:
    if frame.empty:
        columns = {
            "product": pd.Series(dtype="string"),
            "retailer": pd.Series(dtype="string"),
            "region": pd.Series(dtype="string"),
            "date": pd.Series(dtype="datetime64[ns]"),
            f"{side}_promo_price": pd.Series(dtype="Float64"),
            f"{side}_promo_rsp": pd.Series(dtype="Float64"),
            f"{side}_promo_sales": pd.Series(dtype="Float64"),
            f"{side}_promo_time": pd.Series(dtype="Float64"),
            f"{side}_promo_sales_pct": pd.Series(dtype="Float64"),
            f"{side}_brand": pd.Series(dtype="string"),
            f"{side}_manufacturer": pd.Series(dtype="string"),
            f"{side}_productsid": pd.Series(dtype="string"),
            f"{side}_source_rows": pd.Series(dtype="Int64"),
            f"{side}_productsid_count": pd.Series(dtype="Int64"),
        }
        return pd.DataFrame(columns)
    grouped = frame.groupby(list(JOIN_KEY), dropna=False, sort=False)
    aggregated = grouped.agg(
        **{
            f"{side}_promo_price": ("ave_price_quantity", _unique_or_na),
            f"{side}_promo_rsp": ("rsp_on_promo", _unique_or_na),
            f"{side}_promo_sales": ("sales_on_promo", _unique_or_na),
            f"{side}_promo_time": ("time_on_promo", _unique_or_na),
            f"{side}_promo_sales_pct": ("sales_pct_on_promo", _unique_or_na),
            f"{side}_brand": ("brand", _unique_or_na),
            f"{side}_manufacturer": ("manufacturer", _unique_or_na),
            f"{side}_productsid": ("productsid", _join_ids),
            f"{side}_source_rows": ("productsid", "size"),
            f"{side}_productsid_count": ("productsid", "nunique"),
        }
    )
    return aggregated.reset_index()


def pivot_promotion_indicator(promo: pd.DataFrame, config: IntegrationConfig) -> pd.DataFrame:
    """Return one row per Product x Retailer x Region x Date."""
    off_value = config.off_promo_indicator
    on_value = config.on_promo_indicator
    off_slice = promo.loc[promo["promotion_indicator"].eq(off_value)].copy()
    on_slice = promo.loc[promo["promotion_indicator"].eq(on_value)].copy()
    unexpected = promo.loc[~promo["promotion_indicator"].isin([off_value, on_value])]
    unexpected_count = len(unexpected)

    off_wide = _aggregate_indicator_slice(off_slice, "off")
    on_wide = _aggregate_indicator_slice(on_slice, "on")
    wide = off_wide.merge(on_wide, on=list(JOIN_KEY), how="outer")

    wide["promotion_indicator_off_present"] = wide["off_source_rows"].fillna(0).gt(0)
    wide["promotion_indicator_on_present"] = wide["on_source_rows"].fillna(0).gt(0)
    states = []
    for off_present, on_present in zip(
        wide["promotion_indicator_off_present"],
        wide["promotion_indicator_on_present"],
        strict=True,
    ):
        parts: list[str] = []
        if bool(off_present):
            parts.append(str(off_value))
        if bool(on_present):
            parts.append(str(on_value))
        states.append("|".join(parts) if parts else pd.NA)
    wide["promotion_states"] = pd.Series(states, index=wide.index, dtype="string")

    def _merge_ids(row: pd.Series) -> object:
        chunks: list[str] = []
        for column in ("off_productsid", "on_productsid"):
            value = row[column]
            if pd.isna(value):
                continue
            chunks.extend(str(value).split("|"))
        values = sorted({item for item in chunks if item})
        return "|".join(values) if values else pd.NA

    wide["productsid"] = wide.apply(_merge_ids, axis=1).astype("string")
    wide["productsid_count"] = wide["productsid"].fillna("").apply(
        lambda value: 0 if value == "" else len(str(value).split("|"))
    ).astype("Int64")
    off_rows = wide["off_source_rows"].fillna(0)
    on_rows = wide["on_source_rows"].fillna(0)
    wide["price_promo_source_rows"] = (off_rows + on_rows).astype("Int64")
    wide["flag_multiple_source_matches"] = (off_rows.gt(1) | on_rows.gt(1)).astype("boolean")
    wide["flag_ambiguous_product_mapping"] = wide["productsid_count"].gt(1).astype("boolean")
    wide["brand"] = wide["off_brand"].combine_first(wide["on_brand"]).astype("string")
    wide["manufacturer"] = wide["off_manufacturer"].combine_first(wide["on_manufacturer"]).astype("string")
    if unexpected_count:
        wide.attrs["unexpected_indicator_rows"] = unexpected_count
    for column in FLOAT_COLUMNS:
        if column in wide.columns:
            wide[column] = pd.to_numeric(wide[column], errors="coerce").astype("Float64")
    drop_cols = [
        "off_brand",
        "on_brand",
        "off_manufacturer",
        "on_manufacturer",
        "off_productsid",
        "on_productsid",
        "off_source_rows",
        "on_source_rows",
        "off_productsid_count",
        "on_productsid_count",
    ]
    return wide.drop(columns=[column for column in drop_cols if column in wide.columns])
