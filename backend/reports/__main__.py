"""CLI: python -m backend.reports backend/data/"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from backend.reports.assemble import assemble
from backend.reports.loader import load_inputs
from backend.reports.render import render_executive_pdf, render_full_pdf

OUTPUT_JSON = "commercial_opportunity_pulse_v1.json"
OUTPUT_EXEC = "commercial_opportunity_pulse_v1_executive.pdf"
OUTPUT_FULL = "commercial_opportunity_pulse_v1_full.pdf"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Commercial Opportunity Pulse PDF V1: copy frozen Commercial Brain top 3 and Storytelling "
            "Engine narrative into an executive PDF. Does not rescore specialists or claim guaranteed sales."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("backend/data"),
        help="Data root with brain_reports/ and storytelling_reports/ (default backend/data)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for JSON and PDFs (default: <data-root>/opportunity_reports)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Build the JSON in memory and skip writing files",
    )
    return parser


def write_reports(report: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / OUTPUT_JSON
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    exec_path = render_executive_pdf(report, output_dir / OUTPUT_EXEC)
    full_path = render_full_pdf(report, output_dir / OUTPUT_FULL)
    return {
        "json": str(json_path),
        "executive_pdf": str(exec_path),
        "full_pdf": str(full_path),
    }


def run_reports(data_root: str | Path, output_dir: str | Path | None = None, *, write: bool = True) -> dict[str, Any]:
    inputs = load_inputs(data_root)
    report = assemble(inputs)
    paths = {}
    if write:
        target = Path(output_dir) if output_dir else Path(data_root) / "opportunity_reports"
        paths = write_reports(report, target)
        report["report_output_paths"] = paths
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_reports(args.input, args.output_dir, write=not args.no_write)
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    summary = {
        "title": report["document"],
        "period": report["current_period"],
        "headline": report["story"]["headline"],
        "top3_addressable_value": report["top3_sum"]["addressable_value"],
        "opportunities": [
            {
                "rank": item["rank"],
                "product": item["product"],
                "retailer": item["retailer"],
                "region": item["region"],
                "addressable_value": item["addressable_value"],
                "confidence": item["confidence"],
            }
            for item in report["opportunities"]
        ],
        "outputs": report.get("report_output_paths"),
        "causality_claim": report["causality_claim"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
