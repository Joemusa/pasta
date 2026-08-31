"""Shared report assembly for social specialist agents."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.agents.social_common.confidence import insight_confidence
from backend.agents.social_common.models import (
    PeriodWindow,
    QualityBlock,
    SocialConfig,
    SocialObservation,
    SpecialistReport,
)
from backend.agents.social_common.paths import display_path, write_json


def observation_window(observations: list[SocialObservation], config: SocialConfig) -> PeriodWindow:
    dates = sorted(item.published_at for item in observations if item.published_at)
    return PeriodWindow(
        start=dates[0] if dates else None,
        end=dates[-1] if dates else None,
        pos_period_start=config.pos_period_start,
        pos_period_end=config.pos_period_end,
    )


def quality_block(
    observations: list[SocialObservation],
    config: SocialConfig,
    limitations: list[str],
) -> QualityBlock:
    sources = {item.source for item in observations if item.source}
    return QualityBlock(
        evidence_count=len(observations),
        source_count=len(sources),
        date_range=observation_window(observations, config),
        confidence=insight_confidence(observations, config),
        limitations=list(limitations),
    )


def persist_report(report: SpecialistReport, out_path) -> SpecialistReport:
    report.report_output_path = display_path(out_path)
    write_json(out_path, report.to_json_dict())
    return report


def collected_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
