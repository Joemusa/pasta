"""CLI: python -m backend.agents.promotion backend/data/integrated/"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.promotion.agent import run_promotion
from backend.agents.promotion.loader import PromotionLoadError
from backend.agents.promotion.models import PromotionAgentStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Promotion Agent V1: directional Unilever promotional insights on the canonical "
            "integrated dataset. Estimated promotional opportunity only — not causal incrementality."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Canonical *.commercial.csv or directory (default use: backend/data/integrated/)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Root containing promotion_reports/ (defaults next to the integrated/ folder)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional promotion YAML (defaults to backend/schemas/promotion_config.yaml)",
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
        report = run_promotion(
            args.input,
            data_root=args.data_root,
            config_path=args.config,
            write_outputs=not args.no_write,
        )
    except PromotionLoadError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    summary = {
        "status": report.status,
        "version": report.version,
        "frozen": report.frozen,
        "opportunity_label": report.opportunity_label,
        "causality_claim": report.causality_claim,
        "manufacturer": report.manufacturer,
        "current_period": report.current_period,
        "source_integrated_file": report.source_integrated_file,
        "opportunities_emitted": report.opportunities_emitted,
        "total_incremental_value": report.total_incremental_value,
        "total_incremental_volume": report.total_incremental_volume,
        "confidence_distribution": report.confidence_distribution,
        "recommendation_counts": report.recommendation_counts,
        "promotion_uplift_summary": report.promotion_uplift_summary,
        "distribution_primary_count": report.distribution_primary_count,
        "price_primary_count": report.price_primary_count,
        "promotion_primary_count": report.promotion_primary_count,
        "overlap_flag_count": report.overlap_flag_count,
        "outlier_dependent_top_opportunities": report.outlier_dependent_top_opportunities,
        "top_promotional_opportunities": [
            item.model_dump(mode="json") for item in report.top_promotional_opportunities
        ],
        "top_retailers": [item.model_dump(mode="json") for item in report.top_retailers],
        "top_skus": [item.model_dump(mode="json") for item in report.top_skus],
        "top_regions": [item.model_dump(mode="json") for item in report.top_regions],
        "promotion_investment_priorities": [
            item.model_dump(mode="json") for item in report.promotion_investment_priorities
        ],
        "promotion_risks": [item.model_dump(mode="json") for item in report.promotion_risks],
        "limitations": report.limitations,
        "report_output_path": report.report_output_path,
    }
    print(json.dumps(summary, indent=2))
    return 0 if report.status != PromotionAgentStatus.NOT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
