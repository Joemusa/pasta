"""Dominant commercial lever selection. Overlapping specialist values are never summed."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.agents.brain.loader import CommercialRow, DistSignal, PriceSignal, PromoSignal, grain_key
from backend.agents.brain.models import BrainConfig, DominantLever, DoubleCountingRisk

PRICE_GROWTH_RECS = {"LOWER PRICE TEST", "PRICE INCREASE TEST"}
PROMO_GROWTH_RECS = {"PROMOTE", "PROMOTE MORE SELECTIVELY"}
CONF_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


@dataclass
class LeverDecision:
    product: str
    brand: str | None
    retailer: str
    region: str
    dominant: DominantLever
    secondary: DominantLever | None
    overlap: bool
    gross_value: float
    gross_volume: float
    primary_value: float
    primary_volume: float
    secondary_value: float
    secondary_volume: float
    double_counting_risk: DoubleCountingRisk
    confidence: str
    dist: DistSignal | None = None
    price: PriceSignal | None = None
    promo: PromoSignal | None = None
    commercial: CommercialRow | None = None
    complementary: bool = False
    specialist_count: int = 0
    limitations: list[str] = field(default_factory=list)


def _quantified_dist(signal: DistSignal | None, config: BrainConfig) -> bool:
    if signal is None:
        return False
    rate = signal.value_per_store
    attractive = rate is not None and rate >= config.min_value_per_store
    return signal.store_gap >= config.min_store_gap and signal.value >= config.min_primary_value and attractive


def _quantified_price(signal: PriceSignal | None, config: BrainConfig) -> bool:
    if signal is None:
        return False
    return signal.recommendation in PRICE_GROWTH_RECS and signal.value >= config.min_primary_value


def _quantified_promo(signal: PromoSignal | None, config: BrainConfig) -> bool:
    if signal is None:
        return False
    if signal.recommendation not in PROMO_GROWTH_RECS:
        return False
    if signal.value < config.min_primary_value:
        return False
    if signal.subsidising_existing_demand:
        return False
    uplift = signal.volume_uplift_pct
    if uplift is None or uplift < config.min_promo_uplift:
        return False
    return True


def _weaker_confidence(*values: str | None) -> str:
    picked = [item for item in values if item in CONF_RANK]
    if not picked:
        return "LOW"
    return min(picked, key=lambda item: CONF_RANK[item])


def _risk(n_quantified: int, complementary: bool) -> DoubleCountingRisk:
    if n_quantified <= 1:
        return DoubleCountingRisk.NONE
    if complementary:
        return DoubleCountingRisk.MEDIUM
    return DoubleCountingRisk.HIGH


def _promo_beats_price(promo: PromoSignal, price: PriceSignal | None, config: BrainConfig) -> bool:
    if price is None or not _quantified_price(price, config):
        return True
    return promo.value >= price.value * config.promo_vs_price_ratio


def _complementary_dist_promo(
    dist: DistSignal | None,
    promo: PromoSignal | None,
    price: PriceSignal | None,
    config: BrainConfig,
) -> bool:
    """Distribution expansion plus targeted promotion, not two flags for the same sales gap."""
    if not _quantified_dist(dist, config) or not _quantified_promo(promo, config) or dist is None or promo is None:
        return False
    if promo.distribution_primary_lever:
        return False
    if price is not None and price.distribution_primary_lever:
        return False
    if _quantified_price(price, config) and price is not None and price.recommendation == "LOWER PRICE TEST":
        return False
    return True


def decide_lever(
    *,
    dist: DistSignal | None,
    price: PriceSignal | None,
    promo: PromoSignal | None,
    commercial: CommercialRow | None,
    config: BrainConfig,
) -> LeverDecision:
    product = (dist or price or promo).product  # type: ignore[union-attr]
    retailer = (dist or price or promo).retailer  # type: ignore[union-attr]
    region = (dist or price or promo).region  # type: ignore[union-attr]
    brand = None
    if price is not None:
        brand = price.brand
    if brand is None and promo is not None:
        brand = promo.brand
    if brand is None and commercial is not None:
        brand = commercial.brand

    dist_q = _quantified_dist(dist, config)
    price_q = _quantified_price(price, config)
    promo_q = _quantified_promo(promo, config)
    n_q = int(dist_q) + int(price_q) + int(promo_q)
    gross_value = (dist.value if dist else 0.0) + (price.value if price else 0.0) + (promo.value if promo else 0.0)
    gross_volume = (dist.volume if dist else 0.0) + (price.volume if price else 0.0) + (promo.volume if promo else 0.0)
    complementary = _complementary_dist_promo(dist, promo, price, config)
    limitations = [
        "Reported value is the primary lever only; specialist estimates are not summed.",
        "Estimates are directional and are not guaranteed incremental sales.",
    ]
    dist_limiting = dist_q and dist is not None
    if price is not None and price.distribution_primary_lever:
        dist_limiting = dist_limiting or dist_q
    if promo is not None and (promo.distribution_primary_lever or promo.recommendation == "DISTRIBUTION FIRST"):
        dist_limiting = dist_limiting or dist_q

    dominant = DominantLever.INSUFFICIENT_EVIDENCE
    secondary: DominantLever | None = None
    primary_value = 0.0
    primary_volume = 0.0
    secondary_value = 0.0
    secondary_volume = 0.0
    confidence = "LOW"

    if dist_limiting and complementary:
        dominant = DominantLever.MULTI_LEVER
        secondary = DominantLever.PROMOTION
        primary_value = dist.value
        primary_volume = dist.volume
        secondary_value = promo.value if promo else 0.0
        secondary_volume = promo.volume if promo else 0.0
        confidence = _weaker_confidence(dist.confidence if dist else None, promo.confidence if promo else None)
        limitations.append("MULTI-LEVER is complementary (distribution expansion plus targeted promotion), not a sum.")
    elif dist_limiting and dist is not None:
        dominant = DominantLever.DISTRIBUTION
        primary_value = dist.value
        primary_volume = dist.volume
        confidence = dist.confidence
        if promo_q and promo is not None:
            secondary = DominantLever.PROMOTION
            secondary_value = promo.value
            secondary_volume = promo.volume
        elif price_q and price is not None:
            secondary = DominantLever.PRICE
            secondary_value = price.value
            secondary_volume = price.volume
        if n_q > 1:
            limitations.append("Distribution-first: overlapping price/promotion values are not added.")
    elif promo_q and promo is not None and _promo_beats_price(promo, price, config):
        dominant = DominantLever.PROMOTION
        primary_value = promo.value
        primary_volume = promo.volume
        confidence = promo.confidence
        if price_q and price is not None:
            secondary = DominantLever.PRICE
            secondary_value = price.value
            secondary_volume = price.volume
            limitations.append("Promotion selected over price; the two values are not summed.")
    elif price_q and price is not None:
        dominant = DominantLever.PRICE
        primary_value = price.value
        primary_volume = price.volume
        confidence = price.confidence
        if promo_q and promo is not None:
            secondary = DominantLever.PROMOTION
            secondary_value = promo.value
            secondary_volume = promo.volume
        limitations.append("Price selected because distribution is adequate and promotion does not explain the gap.")
    else:
        limitations.append("No specialist lever met the evidence bar for a primary commercial action.")

    if confidence not in CONF_RANK:
        confidence = "LOW"

    return LeverDecision(
        product=product,
        brand=brand,
        retailer=retailer,
        region=region,
        dominant=dominant,
        secondary=secondary,
        overlap=n_q > 1,
        gross_value=round(gross_value, 2),
        gross_volume=round(gross_volume, 4),
        primary_value=round(primary_value, 2),
        primary_volume=round(primary_volume, 4),
        secondary_value=round(secondary_value, 2),
        secondary_volume=round(secondary_volume, 4),
        double_counting_risk=_risk(n_q, complementary),
        confidence=confidence,
        dist=dist,
        price=price,
        promo=promo,
        commercial=commercial,
        complementary=complementary,
        specialist_count=n_q,
        limitations=limitations,
    )


def decide_all(
    *,
    dist: list[DistSignal],
    price: list[PriceSignal],
    promo: list[PromoSignal],
    commercial: dict[str, CommercialRow],
    config: BrainConfig,
) -> list[LeverDecision]:
    keys: dict[str, tuple[str, str, str]] = {}
    dist_map = {grain_key(item.product, item.retailer, item.region): item for item in dist}
    price_map = {grain_key(item.product, item.retailer, item.region): item for item in price}
    promo_map = {grain_key(item.product, item.retailer, item.region): item for item in promo}
    for item in dist:
        keys[grain_key(item.product, item.retailer, item.region)] = (item.product, item.retailer, item.region)
    for item in price:
        keys[grain_key(item.product, item.retailer, item.region)] = (item.product, item.retailer, item.region)
    for item in promo:
        keys[grain_key(item.product, item.retailer, item.region)] = (item.product, item.retailer, item.region)
    decisions = [
        decide_lever(
            dist=dist_map.get(key),
            price=price_map.get(key),
            promo=promo_map.get(key),
            commercial=commercial.get(key),
            config=config,
        )
        for key in sorted(keys)
    ]
    return decisions
