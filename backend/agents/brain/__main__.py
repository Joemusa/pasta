"""CLI: python -m backend.agents.brain backend/data/"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.brain.agent import run_brain
from backend.agents.brain.loader import BrainLoadError
from backend.agents.brain.models import BrainAgentStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Commercial Brain V1: combine frozen Distribution, Price, and Promotion outputs into "
            "three high-impact Unilever actions. Does not sum overlapping levers or claim guaranteed sales."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Data root containing distribution_reports/, price_reports/, promotion_reports/ (backend/data/)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional brain YAML (defaults to backend/schemas/brain_config.yaml)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing the JSON report (still prints a summary)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_brain(args.input, config_path=args.config, write_outputs=not args.no_write)
    except BrainLoadError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    summary = {
        "status": report.status,
        "version": report.version,
        "headline": report.headline,
        "causality_claim": report.causality_claim,
        "current_period": report.current_period,
        "opportunities_emitted": report.opportunities_emitted,
        "total_estimated_value_opportunity": report.total_estimated_value_opportunity,
        "total_estimated_volume_opportunity": report.total_estimated_volume_opportunity,
        "double_counting_conflicts_resolved": report.double_counting_conflicts_resolved,
        "lever_distribution": report.lever_distribution,
        "confidence_distribution": report.confidence_distribution,
        "top_actions": [item.model_dump(mode="json") for item in report.top_actions],
        "top_retailers": [item.model_dump(mode="json") for item in report.top_retailers[:3]],
        "top_skus": [item.model_dump(mode="json") for item in report.top_skus[:3]],
        "top_regions": [item.model_dump(mode="json") for item in report.top_regions[:3]],
        "storytelling": report.storytelling.model_dump(mode="json"),
        "one_slide": report.one_slide.model_dump(mode="json"),
        "limitations": report.limitations,
        "report_output_path": report.report_output_path,
    }
    print(json.dumps(summary, indent=2))
    return 0 if report.status != BrainAgentStatus.NOT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
