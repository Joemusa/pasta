"""Directional promotional recommendations and estimated opportunities.

Not a causal incrementality model. Promo vs non-promo comparisons are directional.
Distribution-primary cases are not recommended as promotions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.agents.promotion.metrics import (
    incremental_value,
    incremental_volume,
    material_distribution_change,
    price_discount_pct,
    summarise_rates,
    uplift_pct,
    value_per_store,
    volume_per_store,
)
from backend.agents.promotion.models import (
    BaselineKind,
    PrimaryLever,
    PromotionConfig,
    PromotionOpportunity,
    PromoIntensity,
    PromoState,
    Recommendation,
)
from backend.agents.promotion.outliers import mad_outlier_mask
from backend.agents.promotion.overlap import OverlapIndex
from backend.agents.promotion.states import (
    classify_intensity,
    classify_promotion_state,
    in_promo_group,
    promotion_type_from_row,
)

PROMOTE_METHODOLOGY = (
    "Estimated promotional opportunity: like-for-like promo vs baseline volume/store gap "
    "times current store count times conservative capture rate. Value uses extra volume "
    "times realised/promotional price. This is directional, not causal incrementality, "
    "and not guaranteed incremental sales."
)
SELECTIVE_METHODOLOGY = (
    "Estimated promotional opportunity with a narrower read: promo response is mixed, "
    "value lags volume, or the grain is only a partial candidate. Capture rate is applied. "
    "Not causal incrementality."
)
MAINTAIN_METHODOLOGY = (
    "Current promotion already shows a directional volume response versus the baseline. "
    "No additional incremental volume is assumed."
)
REDUCE_METHODOLOGY = (
    "Promotion may be subsidising existing demand or the directional promo response is weak. "
    "No incremental volume is assumed."
)
DO_NOT_METHODOLOGY = (
    "High distribution and a strong non-promo/low-intensity baseline with weak promo uplift. "
    "Promotion is not the indicated lever."
)
DIST_METHODOLOGY = (
    "Low distribution plus low sales: distribution is the likely primary lever. "
    "Promotion is not recommended from this comparison."
)
INSUFFICIENT_METHODOLOGY = (
    "No estimated promotional opportunity: promo observations, non-promo/low-intensity "
    "baseline, distribution stability, price coverage, or sample size is insufficient."
)

QUANTIFIED = {Recommendation.PROMOTE, Recommendation.PROMOTE_MORE_SELECTIVELY}
EMITTED = {
    Recommendation.PROMOTE,
    Recommendation.PROMOTE_MORE_SELECTIVELY,
    Recommendation.MAINTAIN_CURRENT_PROMOTION,
    Recommendation.REDUCE_PROMOTION,
    Recommendation.DO_NOT_PROMOTE,
    Recommendation.DISTRIBUTION_FIRST,
}


@dataclass
class Evaluation:
    recommendation: Recommendation
    opportunity: PromotionOpportunity | None = None
    limitations: list[str] = field(default_factory=list)
    primary_lever: PrimaryLever = PrimaryLever.UNCLEAR


def _finite(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if number != number:
        return None
    return number


def _positive_price(value: object) -> float | None:
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def attach_derived(frame: pd.DataFrame, config: PromotionConfig) -> pd.DataFrame:
    out = frame.copy()
    statuses: list[str] = []
    sources: list[str] = []
    intensities: list[str] = []
    intensity_values: list[float | None] = []
    vps: list[float | None] = []
    valps: list[float | None] = []
    for row in out.to_dict(orient="records"):
        status, source = classify_promotion_state(row, config)
        intensity, intensity_value = classify_intensity(row, config)
        statuses.append(status.value)
        sources.append(source)
        intensities.append(intensity.value)
        intensity_values.append(intensity_value)
        vps.append(
            volume_per_store(
                _finite(row.get("sales_volume")),
                _finite(row.get("store_count")),
            )
        )
        valps.append(
            value_per_store(
                _finite(row.get("sales_value")),
                _finite(row.get("store_count")),
            )
        )
    out["promotion_status"] = statuses
    out["promo_source"] = sources
    out["promo_intensity"] = intensities
    out["intensity_value"] = intensity_values
    out["volume_per_store"] = vps
    out["value_per_store"] = valps
    out["realised_price"] = pd.to_numeric(out["pos_current_price"], errors="coerce")
    out["in_promo_group"] = [
        in_promo_group(PromoState(status), PromoIntensity(intensity))
        for status, intensity in zip(statuses, intensities, strict=True)
    ]
    out["in_true_baseline"] = [
        status == PromoState.NON_PROMOTION.value or intensity == PromoIntensity.NONE.value
        for status, intensity in zip(statuses, intensities, strict=True)
    ]
    out["in_low_baseline"] = [intensity == PromoIntensity.LOW.value for intensity in intensities]
    return out


def _peer_store_median(current: pd.DataFrame, product: str, retailer: str, region: str) -> float | None:
    peers = current.loc[
        (current["product"] == product) & (current["retailer"] == retailer) & (current["region"] != region)
    ]
    if len(peers) < 3:
        peers = current.loc[
            (current["product"] == product) & (current["region"] == region) & (current["retailer"] != retailer)
        ]
    stores = pd.to_numeric(peers["store_count"], errors="coerce").dropna()
    if len(stores) < 3:
        return None
    return float(stores.median())


def _peer_volume_median(current: pd.DataFrame, product: str) -> float | None:
    rates = pd.to_numeric(current.loc[current["product"] == product, "volume_per_store"], errors="coerce").dropna()
    if len(rates) < 3:
        return None
    return float(rates.median())


def _distribution_primary(
    *,
    stores: float | None,
    volume: float | None,
    peer_stores: float | None,
    peer_volume_per_store: float | None,
    current_volume_per_store: float | None,
    config: PromotionConfig,
) -> bool:
    if stores is None:
        return False
    low_dist = False
    if peer_stores is not None and peer_stores > 0:
        low_dist = stores < peer_stores * config.low_distribution_ratio
        low_dist = low_dist and (peer_stores - stores) >= config.min_store_gap
    if stores <= 0:
        low_dist = True
    low_sales = False
    if current_volume_per_store is not None and peer_volume_per_store is not None and peer_volume_per_store > 0:
        low_sales = current_volume_per_store < peer_volume_per_store * config.low_sales_ratio
    elif volume is not None and volume <= 0:
        low_sales = True
    return bool(low_dist and low_sales)


def _high_distribution(stores: float | None, peer_stores: float | None, config: PromotionConfig) -> bool:
    if stores is None or peer_stores is None or peer_stores <= 0:
        return False
    return stores >= peer_stores * config.high_distribution_ratio


def _group_rates(frame: pd.DataFrame) -> tuple[list[float], list[float], list[float], list[float]]:
    vol = [float(v) for v in frame["volume_per_store"].tolist() if _finite(v) is not None]
    val = [float(v) for v in frame["value_per_store"].tolist() if _finite(v) is not None]
    stores = [float(v) for v in pd.to_numeric(frame["store_count"], errors="coerce").dropna().tolist()]
    prices = [float(v) for v in pd.to_numeric(frame["realised_price"], errors="coerce").dropna().tolist() if v > 0]
    return vol, val, stores, prices


def _choose_groups(
    product_history: pd.DataFrame,
    *,
    retailer: str,
    region: str,
    config: PromotionConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, BaselineKind, str]:
    empty = product_history.iloc[0:0]
    scopes: list[tuple[str, pd.DataFrame]] = [
        ("own_grain", product_history.loc[
            (product_history["retailer"] == retailer) & (product_history["region"] == region)
        ]),
        ("retailer_peer", product_history.loc[product_history["retailer"] == retailer]),
        ("regional_peer", product_history.loc[product_history["region"] == region]),
        ("sku_network", product_history),
    ]
    for scope_name, scope in scopes:
        promo = scope.loc[scope["in_promo_group"].fillna(False)]
        true_base = scope.loc[scope["in_true_baseline"].fillna(False)]
        low_base = scope.loc[scope["in_low_baseline"].fillna(False)]
        if len(promo) >= config.min_promo_observations and len(true_base) >= config.min_non_promo_observations:
            return promo, true_base, BaselineKind.NON_PROMO, scope_name
        if len(promo) >= config.min_promo_observations and len(low_base) >= config.min_non_promo_observations:
            return promo, low_base, BaselineKind.LOW_PROMO_INTENSITY, scope_name
    return empty, empty, BaselineKind.NONE, "none"


def _outlier_share(frame: pd.DataFrame, threshold: float) -> tuple[pd.Series, float]:
    rates = pd.to_numeric(frame["volume_per_store"], errors="coerce")
    mask = mad_outlier_mask(rates, threshold)
    if mask.empty:
        return mask, 0.0
    return mask, float(mask.mean())


def _confidence(
    *,
    n_weeks: int,
    promo_n: int,
    base_n: int,
    baseline_kind: BaselineKind,
    mixed: bool,
    distribution_primary: bool,
    outliers: list[str],
    recommendation: Recommendation,
    config: PromotionConfig,
) -> str:
    if recommendation == Recommendation.INSUFFICIENT_EVIDENCE:
        return "LOW"
    if (
        n_weeks >= config.min_history_for_high_confidence
        and baseline_kind == BaselineKind.NON_PROMO
        and promo_n >= 4
        and base_n >= 4
        and not mixed
        and not distribution_primary
        and not outliers
    ):
        return "HIGH"
    medium_ok = (
        n_weeks >= config.min_history_for_medium_confidence
        and baseline_kind == BaselineKind.NON_PROMO
        and promo_n >= config.min_promo_observations
        and base_n >= config.min_non_promo_observations
        and not mixed
        and not distribution_primary
        and not outliers
        and recommendation != Recommendation.INSUFFICIENT_EVIDENCE
    )
    if medium_ok:
        return "MEDIUM"
    return "LOW"


def _primary_lever(
    *,
    recommendation: Recommendation,
    dist_primary: bool,
    price_overlap: bool,
    dist_overlap: bool,
) -> PrimaryLever:
    if dist_primary or recommendation == Recommendation.DISTRIBUTION_FIRST:
        return PrimaryLever.DISTRIBUTION
    quantified = recommendation in QUANTIFIED
    if quantified and (price_overlap or dist_overlap):
        return PrimaryLever.OVERLAP
    if quantified or recommendation in {
        Recommendation.MAINTAIN_CURRENT_PROMOTION,
        Recommendation.REDUCE_PROMOTION,
        Recommendation.DO_NOT_PROMOTE,
    }:
        return PrimaryLever.PROMOTION
    if price_overlap:
        return PrimaryLever.PRICE
    return PrimaryLever.UNCLEAR


def evaluate_grain(
    *,
    row: pd.Series,
    current: pd.DataFrame,
    product_history: pd.DataFrame,
    current_date: pd.Timestamp,
    config: PromotionConfig,
    overlap: OverlapIndex | None = None,
) -> Evaluation:
    product = str(row["product"])
    retailer = str(row["retailer"])
    region = str(row["region"])
    brand = None if pd.isna(row.get("brand")) else str(row["brand"])
    stores = _finite(row.get("store_count"))
    sales_volume = _finite(row.get("sales_volume"))
    status = PromoState(str(row["promotion_status"]))
    intensity = PromoIntensity(str(row["promo_intensity"]))
    promo_source = str(row.get("promo_source") or "missing")
    n_weeks = int(product_history.loc[
        (product_history["retailer"] == retailer) & (product_history["region"] == region),
        "date",
    ].nunique()) if len(product_history) else 1
    if n_weeks <= 0:
        n_weeks = 1
    vol = _finite(row.get("volume_per_store"))
    limitations: list[str] = [
        "Findings are estimated promotional opportunity, not causal incrementality.",
        "off_promo_rsp / on_promo_rsp is not used as normal price.",
        "NORMAL_PRICE_UNAVAILABLE.",
        "PROMOTION_TYPE_UNAVAILABLE.",
        "Price history is short and overlapping weeks may share rolling 4 Weeks CY measures.",
    ]
    if promo_source == "missing":
        limitations.append("Promotion metrics are missing; missing is not treated as non-promotion.")
    if status == PromoState.MIXED:
        limitations.append(
            "Promotion Indicator 0 and 1 are both present at this grain; the week is a mixed rolling window."
        )
    ambiguous = row.get("flag_ambiguous_product_mapping")
    if pd.notna(ambiguous) and bool(ambiguous):
        limitations.append("Product name maps to multiple ProductsID values at this grain.")

    overlap = overlap or OverlapIndex()
    price_overlap = overlap.has_price(product, retailer, region)
    dist_overlap = overlap.has_distribution(product, retailer, region)
    if price_overlap:
        limitations.append("Price Agent also emitted an opportunity at this SKU x retailer x region.")
    if dist_overlap:
        limitations.append("Distribution Agent also emitted an opportunity at this SKU x retailer x region.")

    peer_stores = _peer_store_median(current, product, retailer, region)
    peer_vol = _peer_volume_median(current, product)
    dist_primary = _distribution_primary(
        stores=stores,
        volume=sales_volume,
        peer_stores=peer_stores,
        peer_volume_per_store=peer_vol,
        current_volume_per_store=vol,
        config=config,
    )
    if dist_primary:
        limitations.append("Distribution likely primary lever")

    promo_group, base_group, baseline_kind, scope = _choose_groups(
        product_history, retailer=retailer, region=region, config=config
    )
    promo_vol, promo_val, promo_stores_list, promo_prices = _group_rates(promo_group)
    base_vol, base_val, base_stores_list, base_prices = _group_rates(base_group)
    promo_n = len(promo_vol)
    base_n = len(base_vol)
    stat = config.peer_statistic
    promo_vps = summarise_rates(promo_vol, stat)
    base_vps = summarise_rates(base_vol, stat)
    promo_valps = summarise_rates(promo_val, stat)
    base_valps = summarise_rates(base_val, stat)
    vol_uplift = uplift_pct(promo_vps, base_vps)
    val_uplift = uplift_pct(promo_valps, base_valps)
    promo_store_med = summarise_rates(promo_stores_list, "median")
    base_store_med = summarise_rates(base_stores_list, "median")
    dist_changed = material_distribution_change(
        promo_store_med, base_store_med, config.distribution_change_ratio
    )
    if dist_changed:
        limitations.append("Promo and baseline store counts differ materially; uplift is not used.")
    if baseline_kind == BaselineKind.LOW_PROMO_INTENSITY:
        limitations.append(
            "No exclusive non-promo baseline; low promo-intensity observations are used as the baseline."
        )
    if baseline_kind == BaselineKind.NONE:
        limitations.append("Promo and non-promo/low-intensity groups did not both meet the minimum sample size.")
    if scope not in {"own_grain", "none"}:
        limitations.append(f"Uplift uses {scope} like-for-like observations of the same SKU.")

    _, promo_out_share = _outlier_share(promo_group, config.mad_threshold) if len(promo_group) else (None, 0.0)
    _, base_out_share = _outlier_share(base_group, config.mad_threshold) if len(base_group) else (None, 0.0)
    outlier_dominated = promo_out_share > 0.5 or base_out_share > 0.5
    if outlier_dominated:
        limitations.append("Promo or baseline observations are dominated by outliers; uplift is not used.")
    history_rates = pd.to_numeric(
        product_history.loc[
            (product_history["retailer"] == retailer) & (product_history["region"] == region),
            "volume_per_store",
        ],
        errors="coerce",
    )
    outliers: list[str] = []
    if vol is not None and history_rates.notna().sum() >= 3:
        mask = mad_outlier_mask(history_rates, config.mad_threshold)
        last = product_history.loc[
            (product_history["retailer"] == retailer)
            & (product_history["region"] == region)
            & (product_history["date"] == current_date)
        ]
        if len(last) and bool(mask.reindex(last.index, fill_value=False).any()):
            outliers.append("volume_per_store_outlier")
    if promo_out_share > 0 or base_out_share > 0:
        outliers.append("group_volume_outlier")

    on_promo_price = _positive_price(row.get("on_promo_price"))
    off_promo_price = _positive_price(row.get("off_promo_price"))
    realised = _positive_price(row.get("realised_price"))
    currently_high = intensity == PromoIntensity.HIGH or status == PromoState.PROMOTION
    currently_off_or_low = (
        status == PromoState.NON_PROMOTION
        or intensity in {PromoIntensity.NONE, PromoIntensity.LOW}
    )
    current_classifiable = currently_high or currently_off_or_low
    if not current_classifiable:
        limitations.append(
            "This grain has no exclusive promo/non-promo state and no usable promo-intensity band."
        )
    promo_price = on_promo_price or (realised if currently_high else None)
    regular_realised = off_promo_price or summarise_rates(base_prices, "median")
    discount = price_discount_pct(promo_price or realised, regular_realised)
    unit_price = promo_price or realised
    if unit_price is None:
        limitations.append("Price data is missing; incremental value cannot be estimated.")

    mixed = status == PromoState.MIXED
    can_use_uplift = (
        n_weeks >= config.min_weeks_for_recommendation
        and baseline_kind != BaselineKind.NONE
        and promo_n >= config.min_promo_observations
        and base_n >= config.min_non_promo_observations
        and vol_uplift is not None
        and not dist_changed
        and not outlier_dominated
    )
    strong_vol = can_use_uplift and vol_uplift is not None and vol_uplift >= config.strong_volume_uplift_pct
    weak_vol = (not can_use_uplift) or vol_uplift is None or vol_uplift < config.weak_volume_uplift_pct
    strong_val = can_use_uplift and val_uplift is not None and val_uplift >= config.strong_value_uplift_pct
    value_down = val_uplift is not None and val_uplift <= config.weak_value_uplift_pct
    high_dist = _high_distribution(stores, peer_stores, config)
    strong_baseline = (
        base_vps is not None
        and peer_vol is not None
        and peer_vol > 0
        and base_vps >= peer_vol
    )
    subsidising = bool(
        currently_high
        and can_use_uplift
        and (weak_vol or (vol_uplift is not None and vol_uplift > 0 and value_down))
    )
    if subsidising:
        limitations.append("Promotion may be subsidising existing demand.")

    recommendation = Recommendation.INSUFFICIENT_EVIDENCE
    methodology = INSUFFICIENT_METHODOLOGY
    est_vol = 0.0
    est_val = 0.0

    extra = None
    value = None
    if can_use_uplift and vol_uplift is not None and vol_uplift > 0 and not dist_primary:
        extra = incremental_volume(
            baseline_volume_per_store=base_vps,
            volume_uplift=vol_uplift,
            store_count=stores,
            capture_rate=config.capture_rate,
        )
        value = incremental_value(extra, unit_price)

    if dist_primary:
        recommendation = Recommendation.DISTRIBUTION_FIRST
        methodology = DIST_METHODOLOGY
    elif can_use_uplift and high_dist and strong_baseline and weak_vol:
        recommendation = Recommendation.DO_NOT_PROMOTE
        methodology = DO_NOT_METHODOLOGY
    elif can_use_uplift and subsidising:
        recommendation = Recommendation.REDUCE_PROMOTION
        methodology = REDUCE_METHODOLOGY
    elif can_use_uplift and currently_high and weak_vol:
        recommendation = Recommendation.REDUCE_PROMOTION
        methodology = REDUCE_METHODOLOGY
    elif can_use_uplift and currently_off_or_low and strong_vol and extra is not None and value is not None:
        if value >= config.min_value_opportunity:
            recommendation = Recommendation.PROMOTE
            methodology = PROMOTE_METHODOLOGY + f" Capture rate={config.capture_rate}. Baseline={baseline_kind.value}."
            est_vol = round(extra, 4)
            est_val = round(value, 2)
        else:
            recommendation = Recommendation.INSUFFICIENT_EVIDENCE
    elif can_use_uplift and currently_high and strong_vol and strong_val:
        recommendation = Recommendation.MAINTAIN_CURRENT_PROMOTION
        methodology = MAINTAIN_METHODOLOGY
    elif can_use_uplift and currently_high and strong_vol and extra is not None and value is not None:
        if value >= config.min_value_opportunity:
            recommendation = Recommendation.PROMOTE_MORE_SELECTIVELY
            methodology = (
                SELECTIVE_METHODOLOGY + f" Capture rate={config.capture_rate}. Baseline={baseline_kind.value}."
            )
            est_vol = round(extra, 4)
            est_val = round(value, 2)
    elif (
        can_use_uplift
        and current_classifiable
        and currently_off_or_low
        and vol_uplift is not None
        and vol_uplift >= config.weak_volume_uplift_pct
    ):
        if extra is not None and value is not None and value >= config.min_value_opportunity:
            recommendation = Recommendation.PROMOTE_MORE_SELECTIVELY
            methodology = (
                SELECTIVE_METHODOLOGY + f" Capture rate={config.capture_rate}. Baseline={baseline_kind.value}."
            )
            est_vol = round(extra, 4)
            est_val = round(value, 2)

    if recommendation == Recommendation.PROMOTE and price_overlap:
        limitations.append("Promotion effect is flagged separately from any Price Agent price test; not combined.")

    primary = _primary_lever(
        recommendation=recommendation,
        dist_primary=dist_primary,
        price_overlap=price_overlap,
        dist_overlap=dist_overlap,
    )
    confidence = _confidence(
        n_weeks=n_weeks,
        promo_n=promo_n,
        base_n=base_n,
        baseline_kind=baseline_kind,
        mixed=mixed,
        distribution_primary=dist_primary,
        outliers=outliers,
        recommendation=recommendation,
        config=config,
    )
    opportunity = None
    if recommendation in EMITTED:
        period = current_date.strftime("%Y-%m-%d")
        opportunity = PromotionOpportunity(
            opportunity_id=f"{period}|{product}|{retailer}|{region}",
            product=product,
            brand=brand,
            retailer=retailer,
            region=region,
            promo_observations=promo_n,
            non_promo_observations=base_n,
            promo_volume_per_store=None if promo_vps is None else round(promo_vps, 4),
            non_promo_volume_per_store=None if base_vps is None else round(base_vps, 4),
            volume_uplift_pct=None if vol_uplift is None else round(vol_uplift, 4),
            promo_value_per_store=None if promo_valps is None else round(promo_valps, 4),
            non_promo_value_per_store=None if base_valps is None else round(base_valps, 4),
            value_uplift_pct=None if val_uplift is None else round(val_uplift, 4),
            promo_price=None if (promo_price or realised) is None else round(float(promo_price or realised), 4),
            normal_price=None,
            price_discount_pct=None if discount is None else round(discount * 100.0, 4),
            estimated_incremental_volume=est_vol,
            estimated_incremental_value=est_val,
            recommendation=recommendation.value,
            confidence=confidence,  # type: ignore[arg-type]
            outlier_flag=bool(outliers),
            outlier_flags=outliers,
            limitations=limitations,
            methodology=methodology,
            period=period,
            opportunity_label=config.opportunity_label,
            promotion_status=status.value,
            promo_intensity=intensity.value,
            baseline_kind=baseline_kind.value,
            promotion_type=promotion_type_from_row({}).value,
            normal_price_status="NORMAL_PRICE_UNAVAILABLE",
            n_weeks=n_weeks,
            store_count=None if stores is None else round(stores, 4),
            distribution_primary_lever=dist_primary,
            subsidising_existing_demand=subsidising,
            overlaps_price_opportunity=price_overlap,
            overlaps_distribution_opportunity=dist_overlap,
            primary_lever=primary.value,
            mixed_promotion_window=mixed,
        )
    return Evaluation(recommendation, opportunity, limitations, primary)
