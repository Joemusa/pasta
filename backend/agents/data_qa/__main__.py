"""CLI: python -m backend.agents.data_qa INPUT.xlsx."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.data_qa.agent import run_data_qa
from backend.agents.data_qa.models import Status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic Data QA Agent for FMCG POS / commercial extracts.",
    )
    parser.add_argument("input", type=Path, help="CSV or Excel file to validate")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("backend/data"),
        help="Root containing raw/, clean/, and qa_reports/ (default: backend/data)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional QA threshold YAML (defaults to backend/schemas/qa_config.yaml)",
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=None,
        help="Optional canonical schema / alias YAML (defaults to backend/schemas/canonical_schema.yaml)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing clean CSV and QA JSON (still prints the report)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_data_qa(
        args.input,
        data_root=args.data_root,
        config_path=args.config,
        schema_path=args.aliases,
        write_outputs=not args.no_write,
    )
    print(json.dumps(report.to_json_dict(), indent=2))
    return 0 if report.status != Status.FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
