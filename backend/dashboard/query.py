"""Filter frozen Commercial Brain and POS facts for the dashboard. Specialist scores are not recomputed."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from backend.agents.brain.actions import action_headline as brain_headline
from backend.agents.brain.actions import action_why as brain_why
from backend.agents.brain.actions import core_headline, select_top_actions
from backend.agents.brain.aggregations import aggregate_movers, sku_priorities
from backend.agents.brain.models import BrainOpportunity, load_brain_config
from backend.agents.storytelling.narrative import (
    build_headline,
    build_subheadline,
    commercial_implication,
    key_insight,
)
from backend.agents.storytelling.narrative import (
    dominant_lever as story_dominant_lever,
)
from backend.dashboard.loader import DashboardStore

ALL = "all"


def _is_all(value: str | None) -> bool:
    return value is None or str(value).strip() == "" or str(value).strip().casefold() in {ALL, "*"}


def category_of(store: DashboardStore, brand: str | None) -> str | None:
    if not brand:
        return None
    return store.brand_to_category.get(str(brand))


def apply_opportunity_filters(
    store: DashboardStore,
    *,
    category: str | None = None,
    brand: str | None = None,
    product: str | None = None,
    retailer: str | None = None,
    region: str | None = None,
    lever: str | None = None,
) -> list[BrainOpportunity]:
    rows = store.opportunities
    if not _is_all(category):
        rows = [item for item in rows if category_of(store, item.brand) == category]
    if not _is_all(brand):
        rows = [item for item in rows if item.brand == brand]
    if not _is_all(product):
        rows = [item for item in rows if item.product == product]
    if not _is_all(retailer):
        rows = [item for item in rows if item.retailer == retailer]
    if not _is_all(region):
        rows = [item for item in rows if item.region == region]
    if not _is_all(lever):
        rows = [item for item in rows if item.dominant_lever == lever]
    return rows


def apply_pos_filters(
    store: DashboardStore,
    *,
    period: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    product: str | None = None,
    retailer: str | None = None,
    region: str | None = None,
) -> pd.DataFrame:
    frame = store.pos
    if not _is_all(period):
        frame = frame[frame["date"] == period]
    if not _is_all(brand):
        frame = frame[frame["brand"].astype(str) == brand]
    if not _is_all(category):
        mapped = frame["brand"].map(lambda value: store.brand_to_category.get(str(value)))
        frame = frame[mapped == category]
    if not _is_all(product):
        frame = frame[frame["product"].astype(str) == product]
    if not _is_all(retailer):
        frame = frame[frame["retailer"].astype(str) == retailer]
    if not _is_all(region):
        frame = frame[frame["region"].astype(str) == region]
    return frame


def _metric(value: float | None, *, available: bool, unit: str, kind: str) -> dict[str, Any]:
    if not available or value is None or value != value:
        return {"value": None, "available": False, "display": "Not available", "unit": unit, "kind": kind}
    return {"value": float(value), "available": True, "display": float(value), "unit": unit, "kind": kind}


def _maybe(value: Any) -> dict[str, Any]:
    if value is None:
        return {"value": None, "available": False, "display": "Not available"}
    if isinstance(value, float) and value != value:
        return {"value": None, "available": False, "display": "Not available"}
    return {"value": value, "available": True, "display": value}


def _pos_kpis(frame: pd.DataFrame, weekly: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "sales_value": _metric(None, available=False, unit="R", kind="FACT"),
            "sales_volume": _metric(None, available=False, unit="units", kind="FACT"),
            "sales_quantity": _metric(None, available=False, unit="units", kind="FACT"),
            "price_per_kg": _metric(None, available=False, unit="R/kg", kind="FACT"),
            "price_per_volume": _metric(None, available=False, unit="R/volume unit", kind="FACT"),
            "growth_pct": _metric(None, available=False, unit="%", kind="FACT"),
        }
    value = float(pd.to_numeric(frame["sales_value"], errors="coerce").sum())
    volume = float(pd.to_numeric(frame["sales_volume"], errors="coerce").sum())
    price_per_volume = (value / volume) if volume else None
    growth = _wow_growth(weekly)
    return {
        "sales_value": _metric(value, available=True, unit="R", kind="FACT"),
        "sales_volume": _metric(volume, available=True, unit="units", kind="FACT"),
        "sales_quantity": _metric(None, available=False, unit="units", kind="FACT"),
        "price_per_kg": _metric(None, available=False, unit="R/kg", kind="FACT"),
        "price_per_volume": _metric(
            price_per_volume, available=price_per_volume is not None, unit="R/volume unit", kind="FACT"
        ),
        "growth_pct": _metric(growth, available=growth is not None, unit="%", kind="FACT"),
    }


def _wow_growth(weekly: pd.DataFrame) -> float | None:
    if weekly is None or weekly.empty or len(weekly) < 2:
        return None
    ordered = weekly.sort_values("date")
    prior = float(ordered.iloc[-2]["sales_value"])
    latest = float(ordered.iloc[-1]["sales_value"])
    if prior == 0:
        return None
    return (latest - prior) / prior * 100.0


def _weekly_series(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["date", "sales_value", "sales_volume", "price_per_volume", "growth_pct"])
    grouped = (
        frame.groupby("date", as_index=False)
        .agg(sales_value=("sales_value", "sum"), sales_volume=("sales_volume", "sum"))
        .sort_values("date")
    )
    grouped["price_per_volume"] = grouped.apply(
        lambda row: (row["sales_value"] / row["sales_volume"]) if row["sales_volume"] else None,
        axis=1,
    )
    growth: list[float | None] = [None]
    values = grouped["sales_value"].tolist()
    for index in range(1, len(values)):
        prior = values[index - 1]
        growth.append(None if prior == 0 else (values[index] - prior) / prior * 100.0)
    grouped["growth_pct"] = growth
    return grouped


def _opportunity_kpis(opps: list[BrainOpportunity], *, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "addressable_value": _metric(None, available=False, unit="R", kind="OPPORTUNITY"),
            "addressable_volume": _metric(None, available=False, unit="units", kind="OPPORTUNITY"),
        }
    value = sum(item.addressable_value_opportunity for item in opps)
    volume = sum(item.addressable_volume_opportunity for item in opps)
    return {
        "addressable_value": _metric(value, available=True, unit="R", kind="OPPORTUNITY"),
        "addressable_volume": _metric(volume, available=True, unit="units", kind="OPPORTUNITY"),
    }


def _story_from_actions(
    opps: list[BrainOpportunity], actions: list[dict[str, Any]], totals: dict[str, float]
) -> dict[str, Any]:
    lever = story_dominant_lever(actions) if actions else "INSUFFICIENT EVIDENCE"
    if len(actions) >= 3:
        headline = build_headline(actions[:3], lever)
        subheadline = build_subheadline(actions[:3], lever)
        insight = key_insight(actions[:3], lever)
        implication = commercial_implication(actions[:3], lever)
    elif actions:
        headline = build_headline(actions, lever)
        n = len(actions)
        subheadline = (
            f"{n} filtered action(s) represent R{totals['value']:,.0f} of addressable value. "
            "This is directional opportunity, not guaranteed incremental sales."
        )
        insight = (
            "The filtered Commercial Brain ranking is the story; overlapping specialist values are not added together."
        )
        implication = commercial_implication(actions, lever)
    else:
        headline = "No Commercial Brain actions match the current filters"
        subheadline = "Addressable opportunity is not guaranteed incremental sales."
        insight = (
            "Filters removed every ranked action. Facts below still reflect the filtered POS slice where available."
        )
        implication = "Clear filters to return to the Unilever commercial story."
        lever = "INSUFFICIENT EVIDENCE"
    region = actions[0]["region"] if actions else None
    core = core_headline(opps, [], region)
    return {
        "headline": headline,
        "subheadline": subheadline,
        "key_insight": insight,
        "commercial_implication": implication,
        "dominant_lever": lever,
        "brain_core_message": core,
        "kind": "RECOMMENDATION",
        "disclaimer": (
            "Addressable opportunity is directional and not guaranteed incremental sales. "
            "Sentiment and macro context do not cause POS gaps."
        ),
    }


def _action_payload(opp: BrainOpportunity, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "opportunity_id": opp.opportunity_id,
        "headline": brain_headline(opp),
        "lever": opp.dominant_lever,
        "product": opp.product,
        "brand": opp.brand,
        "retailer": opp.retailer,
        "region": opp.region,
        "current_sales": _maybe(opp.current_sales),
        "addressable_value": opp.addressable_value_opportunity,
        "addressable_volume": opp.addressable_volume_opportunity,
        "confidence": opp.confidence,
        "why": brain_why(opp),
        "recommended_action": opp.recommended_action,
        "store_gap": _maybe(opp.distribution_gap),
        "value_per_store": _maybe(opp.sales_per_store),
        "volume_per_store": _maybe(opp.volume_per_store),
        "current_stores": _maybe(opp.distribution_stores),
        "price_signal": _maybe(opp.price_signal),
        "promotion_signal": _maybe(opp.promotion_signal),
        "double_counting_risk": opp.double_counting_risk,
        "evidence": list(opp.evidence),
        "priority_score": opp.priority_score,
        "kind": "OPPORTUNITY",
    }


def _from_brain_action(action, rank: int, opps: list[BrainOpportunity]) -> dict[str, Any]:
    match = next(
        (
            item
            for item in opps
            if item.product == action.product and item.retailer == action.retailer and item.region == action.region
        ),
        None,
    )
    if match is not None:
        payload = _action_payload(match, rank)
        payload["headline"] = action.headline
        payload["why"] = action.why
        payload["evidence"] = list(action.evidence)
        payload["recommended_action"] = action.recommended_action
        return payload
    return {
        "rank": rank,
        "opportunity_id": None,
        "headline": action.headline,
        "lever": action.lever,
        "product": action.product,
        "brand": action.brand,
        "retailer": action.retailer,
        "region": action.region,
        "current_sales": _maybe(action.current_sales),
        "addressable_value": action.addressable_value,
        "addressable_volume": action.addressable_volume,
        "confidence": action.confidence,
        "why": action.why,
        "recommended_action": action.recommended_action,
        "store_gap": _maybe(None),
        "value_per_store": _maybe(None),
        "volume_per_store": _maybe(None),
        "current_stores": _maybe(None),
        "price_signal": _maybe(None),
        "promotion_signal": _maybe(None),
        "double_counting_risk": None,
        "evidence": list(action.evidence),
        "priority_score": action.priority_score,
        "kind": "OPPORTUNITY",
    }


def filter_options(store: DashboardStore, filters: dict[str, str | None]) -> dict[str, list[str]]:
    def _pos(**overrides: str | None) -> pd.DataFrame:
        merged = {
            "period": filters.get("period"),
            "category": filters.get("category"),
            "brand": filters.get("brand"),
            "product": filters.get("product"),
            "retailer": filters.get("retailer"),
            "region": filters.get("region"),
        }
        merged.update(overrides)
        return apply_pos_filters(store, **merged)

    period_for_pos = filters.get("period")
    if _is_all(period_for_pos):
        period_for_pos = None
    category_pos = _pos(period=period_for_pos, category=None, brand=None, product=None)
    brand_pos = _pos(period=period_for_pos, brand=None, product=None)
    product_pos = _pos(period=period_for_pos, product=None)
    retailer_pos = _pos(period=period_for_pos, retailer=None)
    region_pos = _pos(period=period_for_pos, region=None)
    brands = sorted({str(item) for item in brand_pos["brand"].dropna().unique() if str(item) not in {"nan", ""}})
    products = sorted({str(item) for item in product_pos["product"].dropna().unique()})
    retailers = sorted({str(item) for item in retailer_pos["retailer"].dropna().unique()})
    regions = sorted({str(item) for item in region_pos["region"].dropna().unique()})
    categories = sorted(
        {
            store.brand_to_category[str(item)]
            for item in category_pos["brand"].dropna().unique()
            if str(item) in store.brand_to_category
        }
    )
    opps = apply_opportunity_filters(
        store,
        category=filters.get("category"),
        brand=filters.get("brand"),
        product=filters.get("product"),
        retailer=filters.get("retailer"),
        region=filters.get("region"),
        lever=None,
    )
    levers = sorted({item.dominant_lever for item in opps})
    return {
        "period": list(store.period_list),
        "category": categories,
        "brand": brands,
        "product": products,
        "retailer": retailers,
        "region": regions,
        "lever": levers,
    }


def assemble(
    store: DashboardStore,
    *,
    period: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    product: str | None = None,
    retailer: str | None = None,
    region: str | None = None,
    lever: str | None = None,
    top_n: int = 3,
) -> dict[str, Any]:
    config = load_brain_config()
    top_n = 10 if int(top_n) >= 10 else 3
    pos_period = store.current_period if _is_all(period) else period
    pos_slice = apply_pos_filters(
        store, period=pos_period, category=category, brand=brand, product=product, retailer=retailer, region=region
    )
    pos_history = apply_pos_filters(
        store, period=None, category=category, brand=brand, product=product, retailer=retailer, region=region
    )
    weekly = _weekly_series(pos_history)
    opps = apply_opportunity_filters(
        store, category=category, brand=brand, product=product, retailer=retailer, region=region, lever=lever
    )
    opportunity_available = _is_all(period) or period == store.current_period
    visible_opps = opps if opportunity_available else []
    growth_weeks = weekly
    if not _is_all(period) and not weekly.empty:
        growth_weeks = weekly[weekly["date"] <= str(pos_period)]
    kpis = _pos_kpis(pos_slice, growth_weeks)
    kpis.update(_opportunity_kpis(visible_opps, available=opportunity_available))
    brain_actions = select_top_actions(visible_opps, config)
    featured = [_from_brain_action(item, index, opps) for index, item in enumerate(brain_actions, start=1)]
    if top_n <= 3:
        table = featured[:]
    else:
        table = []
        for index, item in enumerate(sku_priorities(visible_opps, 10), start=1):
            match = next(
                (
                    row
                    for row in visible_opps
                    if row.product == item.product and row.retailer == item.retailer and row.region == item.region
                ),
                None,
            )
            if match is None:
                continue
            row = _action_payload(match, index)
            overlay = next((card for card in featured if card["opportunity_id"] == match.opportunity_id), None)
            if overlay:
                row["headline"] = overlay["headline"]
                row["why"] = overlay["why"]
            table.append(row)
    action_dicts = [
        {
            "rank": item.rank,
            "lever": item.lever,
            "headline": item.headline,
            "product": item.product,
            "brand": item.brand,
            "retailer": item.retailer,
            "region": item.region,
            "addressable_value": item.addressable_value,
            "addressable_volume": item.addressable_volume,
            "confidence": item.confidence,
            "why": item.why,
            "recommended_action": item.recommended_action,
        }
        for item in brain_actions
    ]
    totals = {
        "value": sum(item.addressable_value_opportunity for item in visible_opps),
        "volume": sum(item.addressable_volume_opportunity for item in visible_opps),
    }
    story = _story_from_actions(visible_opps, action_dicts, totals)
    pos_sales_region = pos_slice.groupby("region")["sales_value"].sum().to_dict() if not pos_slice.empty else {}
    pos_vol_region = pos_slice.groupby("region")["sales_volume"].sum().to_dict() if not pos_slice.empty else {}
    pos_sales_retailer = pos_slice.groupby("retailer")["sales_value"].sum().to_dict() if not pos_slice.empty else {}
    pos_vol_retailer = pos_slice.groupby("retailer")["sales_volume"].sum().to_dict() if not pos_slice.empty else {}
    wow_by_region = _group_wow(pos_history, "region") if not pos_history.empty else {}
    wow_by_retailer = _group_wow(pos_history, "retailer") if not pos_history.empty else {}
    stores_by_region = _median_stores(pos_slice, "region")
    stores_by_retailer = _median_stores(pos_slice, "retailer")
    retailers, regions = aggregate_movers(visible_opps) if opportunity_available else ([], [])
    region_cards = [
        _mover(
            item,
            sales=pos_sales_region.get(item.name),
            volume=pos_vol_region.get(item.name),
            growth=wow_by_region.get(item.name),
            distribution=stores_by_region.get(item.name),
        )
        for item in regions[:12]
    ]
    retailer_cards = [
        _mover(
            item,
            sales=pos_sales_retailer.get(item.name),
            volume=pos_vol_retailer.get(item.name),
            growth=wow_by_retailer.get(item.name),
            distribution=stores_by_retailer.get(item.name),
        )
        for item in retailers[:12]
    ]
    options = filter_options(
        store,
        {
            "period": period,
            "category": category,
            "brand": brand,
            "product": product,
            "retailer": retailer,
            "region": region,
        },
    )
    lever_key = None if _is_all(lever) else str(lever)
    return {
        "manufacturer": store.manufacturer,
        "filters": {
            "period": ALL if _is_all(period) else period,
            "category": ALL if _is_all(category) else category,
            "brand": ALL if _is_all(brand) else brand,
            "product": ALL if _is_all(product) else product,
            "retailer": ALL if _is_all(retailer) else retailer,
            "region": ALL if _is_all(region) else region,
            "lever": ALL if _is_all(lever) else lever,
            "top_n": top_n,
        },
        "options": {key: [ALL, *values] for key, values in options.items()},
        "kpis": kpis,
        "trends": {
            "periods": weekly["date"].tolist() if not weekly.empty else [],
            "note": f"{store.pos_weeks} POS weeks available. This is not a 12-month trend.",
            "sales_value": _trend_points(weekly, "sales_value"),
            "sales_volume": _trend_points(weekly, "sales_volume"),
            "price_per_volume": _trend_points(weekly, "price_per_volume"),
            "growth_pct": _trend_points(weekly, "growth_pct"),
        },
        "story": story,
        "top_actions": featured,
        "opportunities": table,
        "regions": region_cards,
        "retailers": retailer_cards,
        "products": _product_rollups(store, pos_slice, visible_opps),
        "price": _specialist_view(store, "price", lever_key, category, brand, product, retailer, region, pos_period),
        "promotion": _specialist_view(
            store, "promotion", lever_key, category, brand, product, retailer, region, pos_period
        ),
        "distribution": _distribution_view(
            store, visible_opps, lever_key, category, brand, product, retailer, region
        ),
        "macro": _macro_block(store),
        "social": {"status": store.social_status, "detail": store.social_detail, "kind": "OBSERVATION"},
        "quality": {
            "current_period": store.current_period,
            "pos_weeks": store.pos_weeks,
            "period_list": store.period_list,
            "price_promotion_weeks": store.price_promo_weeks,
            "qa_status": store.qa_status,
            "social_status": store.social_status,
            "macro_status": "available" if store.macro else "absent",
            "limitations": store.limitations[:12],
            "sku_identity": "product name (ProductsID is not the canonical join key)",
            "opportunity_label": store.brain.get("opportunity_label"),
            "causality_claim": store.brain.get("causality_claim") or "none",
        },
        "sources": store.sources,
        "causality_claim": "none",
        "labels": {
            "FACT": "POS extract",
            "OBSERVATION": "Specialist observation",
            "OPPORTUNITY": "Addressable, not guaranteed",
            "RECOMMENDATION": "Brief / test, not booked sales",
        },
    }


def _trend_points(weekly: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    if weekly.empty:
        return []
    points = []
    for _, row in weekly.iterrows():
        value = row[column]
        available = value is not None and value == value
        points.append(
            {
                "period": str(row["date"]),
                "value": None if not available else float(value),
                "available": bool(available),
            }
        )
    return points


def _group_wow(frame: pd.DataFrame, key: str) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    if frame.empty or key not in frame.columns:
        return out
    weekly = frame.groupby([key, "date"], as_index=False)["sales_value"].sum().sort_values(["date"])
    for name, group in weekly.groupby(key):
        ordered = group.sort_values("date")
        if len(ordered) < 2:
            out[str(name)] = None
            continue
        prior = float(ordered.iloc[-2]["sales_value"])
        latest = float(ordered.iloc[-1]["sales_value"])
        out[str(name)] = None if prior == 0 else (latest - prior) / prior * 100.0
    return out


def _median_stores(frame: pd.DataFrame, key: str) -> dict[str, float]:
    if frame.empty or key not in frame.columns or "store_count" not in frame.columns:
        return {}
    numeric = pd.to_numeric(frame["store_count"], errors="coerce")
    grouped = frame.assign(_stores=numeric).groupby(key)["_stores"].median()
    return {str(name): float(value) for name, value in grouped.items() if value == value}


def _mover(item, *, sales=None, volume=None, growth=None, distribution=None) -> dict[str, Any]:
    return {
        "name": item.name,
        "sales": _maybe(None if sales is None or sales != sales else float(sales)),
        "volume": _maybe(None if volume is None or volume != volume else float(volume)),
        "growth": _maybe(None if growth is None or growth != growth else float(growth)),
        "distribution": _maybe(None if distribution is None or distribution != distribution else float(distribution)),
        "opportunity_value": item.addressable_value,
        "opportunity_volume": item.addressable_volume,
        "dominant_lever": item.dominant_lever,
        "kind": "OPPORTUNITY",
    }


def _product_rollups(store: DashboardStore, pos: pd.DataFrame, opps: list[BrainOpportunity]) -> list[dict[str, Any]]:
    value_by_product: Counter[str] = Counter()
    volume_by_product: Counter[str] = Counter()
    brand_from_pos: dict[str, str | None] = {}
    if not pos.empty:
        grouped = pos.groupby("product", dropna=False)[["sales_value", "sales_volume"]].sum()
        for name, row in grouped.iterrows():
            value_by_product[str(name)] += float(row["sales_value"] or 0)
            volume_by_product[str(name)] += float(row["sales_volume"] or 0)
        brands = pos.groupby("product")["brand"].agg(
            lambda series: next((str(item) for item in series if item == item), None)
        )
        brand_from_pos = {str(name): value for name, value in brands.items()}
    opp_value: Counter[str] = Counter()
    brands: dict[str, str | None] = dict(brand_from_pos)
    for item in opps:
        opp_value[item.product] += item.addressable_value_opportunity
        brands[item.product] = item.brand
    names = sorted(set(value_by_product) | set(opp_value), key=lambda name: -opp_value[name])[:20]
    return [
        {
            "product": name,
            "brand": brands.get(name),
            "category": category_of(store, brands.get(name)),
            "sku_identity": name,
            "sales_value": _maybe(value_by_product.get(name)),
            "sales_volume": _maybe(volume_by_product.get(name)),
            "opportunity_value": opp_value.get(name) or 0.0,
        }
        for name in names
    ]


def _match_specialist(
    row: dict[str, Any],
    store: DashboardStore,
    *,
    category: str | None,
    brand: str | None,
    product: str | None,
    retailer: str | None,
    region: str | None,
    period: str | None,
) -> bool:
    sku = str(row.get("product") or row.get("sku") or "")
    row_brand = row.get("brand")
    row_retailer = str(row.get("retailer") or "")
    row_region = str(row.get("region") or "")
    row_period = str(row.get("period") or "")
    if product and sku != product:
        return False
    if brand and row_brand != brand:
        return False
    if retailer and row_retailer != retailer:
        return False
    if region and row_region != region:
        return False
    if category:
        mapped = store.brand_to_category.get(str(row_brand)) if row_brand else None
        if mapped != category:
            return False
    if period and row_period and row_period != period:
        return False
    return True


def _specialist_view(
    store: DashboardStore,
    kind: str,
    lever: str | None,
    category: str | None,
    brand: str | None,
    product: str | None,
    retailer: str | None,
    region: str | None,
    period: str | None,
) -> list[dict[str, Any]]:
    expected = "PRICE" if kind == "price" else "PROMOTION"
    if lever and lever != expected:
        return []
    payload = store.price if kind == "price" else store.promotion
    rows = payload.get("opportunities") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not _match_specialist(
            row,
            store,
            category=None if _is_all(category) else category,
            brand=None if _is_all(brand) else brand,
            product=None if _is_all(product) else product,
            retailer=None if _is_all(retailer) else retailer,
            region=None if _is_all(region) else region,
            period=period,
        ):
            continue
        if kind == "price":
            out.append(
                {
                    "product": row.get("product"),
                    "brand": row.get("brand"),
                    "retailer": row.get("retailer"),
                    "region": row.get("region"),
                    "current_price": _maybe(row.get("current_price")),
                    "price_per_kg": _maybe(None),
                    "benchmark_price": _maybe(row.get("benchmark_price")),
                    "price_difference_pct": _maybe(row.get("price_difference_pct")),
                    "price_signal": _maybe(row.get("price_signal")),
                    "recommendation": _maybe(row.get("recommendation")),
                    "confidence": row.get("confidence"),
                    "opportunity_value": _maybe(row.get("estimated_value_opportunity")),
                    "normal_price": _maybe(None),
                    "kind_signal": "PRICE SIGNAL",
                    "kind_recommendation": "PRICE RECOMMENDATION",
                }
            )
        else:
            out.append(
                {
                    "product": row.get("product"),
                    "brand": row.get("brand"),
                    "retailer": row.get("retailer"),
                    "region": row.get("region"),
                    "recommendation": _maybe(row.get("recommendation")),
                    "confidence": row.get("confidence"),
                    "volume_uplift_pct": _maybe(row.get("volume_uplift_pct")),
                    "promo_observations": _maybe(row.get("promo_observations")),
                    "opportunity_value": _maybe(row.get("estimated_incremental_value")),
                    "normal_price": _maybe(row.get("normal_price")),
                    "promotion_type": _maybe(row.get("promotion_type")),
                    "kind": "OBSERVATION",
                }
            )
        if len(out) >= 25:
            break
    return out


def _distribution_view(
    store: DashboardStore,
    opps: list[BrainOpportunity],
    lever: str | None,
    category: str | None,
    brand: str | None,
    product: str | None,
    retailer: str | None,
    region: str | None,
) -> list[dict[str, Any]]:
    if lever and lever != "DISTRIBUTION":
        return []
    out: list[dict[str, Any]] = []
    for item in opps:
        if item.dominant_lever != "DISTRIBUTION":
            continue
        if product and not _is_all(product) and item.product != product:
            continue
        if brand and not _is_all(brand) and item.brand != brand:
            continue
        if retailer and not _is_all(retailer) and item.retailer != retailer:
            continue
        if region and not _is_all(region) and item.region != region:
            continue
        if category and not _is_all(category) and category_of(store, item.brand) != category:
            continue
        grain = store.distribution_index.get((item.product, item.retailer, item.region), {})
        out.append(
            {
                "product": item.product,
                "brand": item.brand,
                "retailer": item.retailer,
                "region": item.region,
                "current_stores": _maybe(grain.get("current_stores", item.distribution_stores)),
                "benchmark_stores": _maybe(grain.get("benchmark_stores")),
                "store_gap": _maybe(grain.get("store_gap", item.distribution_gap)),
                "value_per_store": _maybe(grain.get("value_per_store", item.sales_per_store)),
                "volume_per_store": _maybe(grain.get("volume_per_store", item.volume_per_store)),
                "opportunity_value": _maybe(item.addressable_value_opportunity),
                "confidence": item.confidence,
                "kind": "OPPORTUNITY",
            }
        )
        if len(out) >= 25:
            break
    return out


def _macro_block(store: DashboardStore) -> dict[str, Any]:
    pack = store.macro or {}
    if not pack:
        return {"included": False, "role": "absent", "status": "absent", "kind": "OBSERVATION"}
    return {
        "included": True,
        "role": "supporting_context",
        "status": "available",
        "signal": pack.get("signal"),
        "evidence": pack.get("evidence"),
        "direction": pack.get("direction"),
        "confidence": pack.get("confidence"),
        "commercial_implication": pack.get("commercial_implication"),
        "disclaimer": (
            "Macro context is supporting background only. It does not cause or recalculate POS opportunities."
        ),
        "kind": "OBSERVATION",
    }


def opportunity_detail(store: DashboardStore, opportunity_id: str) -> dict[str, Any] | None:
    match = next((item for item in store.opportunities if item.opportunity_id == opportunity_id), None)
    if match is None:
        return None
    config = load_brain_config()
    actions = select_top_actions([match], config)
    payload = _action_payload(match, 1)
    if actions:
        payload["headline"] = actions[0].headline
        payload["why"] = actions[0].why
        payload["evidence"] = list(actions[0].evidence)
    grain = store.distribution_index.get((match.product, match.retailer, match.region), {})
    payload["benchmark_stores"] = _maybe(grain.get("benchmark_stores"))
    payload["limitations"] = list(match.limitations)
    payload["secondary_lever"] = match.secondary_lever
    payload["overlap"] = match.overlap
    payload["price_row"] = store.price_index.get((match.product, match.retailer, match.region))
    payload["promotion_row"] = store.promotion_index.get((match.product, match.retailer, match.region))
    return payload
