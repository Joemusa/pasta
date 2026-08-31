"""CLI: python -m backend.agents.distribution backend/data/clean/"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.distribution.agent import run_distribution
from backend.agents.distribution.loader import DistributionLoadError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic Distribution Agent for cleaned Unilever POS extracts.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Cleaned CSV (*.clean.csv) or a directory of cleaned files (default use: backend/data/clean/)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Root containing distribution_reports/ (defaults next to the clean/ folder)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional distribution YAML (defaults to backend/schemas/distribution_config.yaml)",
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
        report = run_distribution(
            args.input,
            data_root=args.data_root,
            config_path=args.config,
            write_outputs=not args.no_write,
        )
    except DistributionLoadError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    summary = {
        "opportunity_label": report.opportunity_label,
        "manufacturer": report.manufacturer,
        "current_period": report.current_period,
        "source_clean_file": report.source_clean_file,
        "total_value_opportunity": report.total_value_opportunity,
        "total_volume_opportunity": report.total_volume_opportunity,
        "opportunities_emitted": report.opportunities_emitted,
        "confidence_distribution": report.confidence_distribution,
        "top_retailers": [item.model_dump(mode="json") for item in report.top_retailers],
        "top_regions": [item.model_dump(mode="json") for item in report.top_regions],
        "top_skus": [item.model_dump(mode="json") for item in report.top_skus],
        "top_opportunities": [item.model_dump(mode="json") for item in report.top_opportunities],
        "limitations": report.limitations,
        "report_output_path": report.report_output_path,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
