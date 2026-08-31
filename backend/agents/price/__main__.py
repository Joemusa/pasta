"""CLI: python -m backend.agents.price backend/data/integrated/"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.price.agent import run_price
from backend.agents.price.loader import PriceLoadError
from backend.agents.price.models import PriceAgentStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Price Agent V1: directional Unilever price insights on the canonical integrated dataset. "
            "Not a causal elasticity model."
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
        help="Root containing price_reports/ (defaults next to the integrated/ folder)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional price YAML (defaults to backend/schemas/price_config.yaml)",
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
        report = run_price(
            args.input,
            data_root=args.data_root,
            config_path=args.config,
            write_outputs=not args.no_write,
        )
    except PriceLoadError as exc:
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
        "total_value_opportunity": report.total_value_opportunity,
        "total_volume_opportunity": report.total_volume_opportunity,
        "confidence_distribution": report.confidence_distribution,
        "recommendation_counts": report.recommendation_counts,
        "price_signal_summary": report.price_signal_summary,
        "top_price_opportunities": [item.model_dump(mode="json") for item in report.top_price_opportunities],
        "top_retailers": [item.model_dump(mode="json") for item in report.top_retailers],
        "top_skus": [item.model_dump(mode="json") for item in report.top_skus],
        "top_regions": [item.model_dump(mode="json") for item in report.top_regions],
        "limitations": report.limitations,
        "report_output_path": report.report_output_path,
    }
    print(json.dumps(summary, indent=2))
    return 0 if report.status != PriceAgentStatus.NOT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
