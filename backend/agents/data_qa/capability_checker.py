"""Decide which downstream agents can run from QA'd data."""

from __future__ import annotations

import logging

import pandas as pd

from backend.agents.data_qa.models import Capabilities, QAConfig

logger = logging.getLogger("backend.agents.data_qa.capability_checker")

PRICE_FIELDS = ("current_price", "normal_price")
PROMO_FIELDS = ("percent_time_on_promo", "percent_sales_on_promo", "promotion_flag")


def _non_null(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool(frame[column].notna().any())


def _any_non_null(frame: pd.DataFrame, columns: tuple[str, ...]) -> bool:
    return any(_non_null(frame, column) for column in columns)


def distinct_dates(frame: pd.DataFrame) -> int:
    if "date" not in frame.columns:
        return 0
    return int(pd.to_datetime(frame["date"], errors="coerce").nunique(dropna=True))


def analysis_ready(frame: pd.DataFrame, has_critical_blocker: bool) -> bool:
    if has_critical_blocker:
        return False
    if frame.empty:
        return False
    if "date" not in frame.columns or not frame["date"].notna().any():
        return False
    has_identity = _non_null(frame, "product") or _non_null(frame, "sku")
    if not has_identity:
        return False
    if not _non_null(frame, "retailer"):
        return False
    if not _non_null(frame, "sales_value"):
        return False
    if not _non_null(frame, "sales_volume"):
        return False
    return True


def check_capabilities(
    frame: pd.DataFrame,
    config: QAConfig,
    *,
    ready: bool,
) -> Capabilities:
    n_dates = distinct_dates(frame)
    distribution = _non_null(frame, "store_count")
    price = _any_non_null(frame, PRICE_FIELDS) and n_dates >= config.min_history_for_price_agent
    promotion = _any_non_null(frame, PROMO_FIELDS) and n_dates >= config.min_history_for_promo_agent
    macro_overlay = n_dates >= 1
    social_evidence = _non_null(frame, "brand") or _non_null(frame, "product")
    commercial_brain = ready
    capabilities = Capabilities(
        distribution=distribution,
        price=price,
        promotion=promotion,
        macro_overlay=macro_overlay,
        social_evidence=social_evidence,
        commercial_brain=commercial_brain,
    )
    logger.info("capabilities %s", capabilities.model_dump())
    return capabilities
