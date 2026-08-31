"""CLI: python -m backend.agents.integration"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.integration.agent import run_integration
from backend.agents.integration.loader import IntegrationLoadError
from backend.agents.integration.models import IntegrationStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministic Commercial Data Integration Layer. "
            "Joins cleaned POS to Unilever price/promotion on Product + Retailer + Region + Date."
        ),
    )
    parser.add_argument(
        "--pos",
        type=Path,
        default=None,
        help="Cleaned POS CSV (*.clean.csv) or directory (default: path in integration_config.yaml)",
    )
    parser.add_argument(
        "--price-promo",
        type=Path,
        default=None,
        help="Committed Unilever price/promotion CSV (default: path in integration_config.yaml)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Root containing integrated/ and integration_reports/ (defaults next to the clean/ folder)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional integration YAML (defaults to backend/schemas/integration_config.yaml)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing the canonical CSV and JSON report (still prints a summary)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _canonical, report = run_integration(
            args.pos,
            args.price_promo,
            data_root=args.data_root,
            config_path=args.config,
            write_outputs=not args.no_write,
        )
    except IntegrationLoadError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    summary = {
        "status": report.status,
        "grain": report.grain,
        "join_key": report.join_key,
        "pos_source_file": report.pos_source_file,
        "price_promo_source_file": report.price_promo_source_file,
        "canonical_output_path": report.canonical_output_path,
        "pos_row_count": report.pos_row_count,
        "price_promo_row_count": report.price_promo_row_count,
        "canonical_row_count": report.canonical_row_count,
        "overlapping_weeks": report.overlapping_weeks,
        "non_overlapping_weeks": report.non_overlapping_weeks,
        "match_rate_pos": report.match_rate_pos,
        "match_rate_unilever_pos": report.match_rate_unilever_pos,
        "match_rate_unilever_overlapping_weeks": report.match_rate_unilever_overlapping_weeks,
        "unmatched_pos_records": report.unmatched_pos_records,
        "unmatched_price_promo_records": report.unmatched_price_promo_records,
        "price_enabled_rows": report.price_enabled_rows,
        "promotion_enabled_rows": report.promotion_enabled_rows,
        "july_26_pos_rows_retained": report.july_26_pos_rows_retained,
        "limitations": report.limitations,
        "report_output_path": report.report_output_path,
    }
    print(json.dumps(summary, indent=2))
    return 0 if report.status != IntegrationStatus.NOT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
