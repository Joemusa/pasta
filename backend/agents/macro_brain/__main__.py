"""CLI: python -m backend.agents.macro_brain backend/data/"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.macro_brain.agent import run_macro_brain
from backend.agents.macro_common.catalog import MacroLoadError
from backend.agents.macro_common.models import MacroAgentStatus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MacroContextBrain: attach four specialist macro agents as supporting context to "
            "Commercial Brain findings. Does not recalculate POS opportunities or claim causality."
        )
    )
    parser.add_argument("input", type=Path, help="Data root with brain_reports/ and macro_observations/")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_macro_brain(args.input, config_path=args.config, write_outputs=not args.no_write)
    except (MacroLoadError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    summary = {
        "agent": report.agent,
        "status": report.status,
        "verdict": report.verdict,
        "overall_environment": report.overall_environment,
        "pos_story": report.pos_story.model_dump(mode="json"),
        "fmcg_implications": report.fmcg_implications,
        "sources": report.sources,
        "data_gaps": report.data_gaps,
        "report_output_path": report.report_output_path,
        "causality_claim": report.causality_claim,
    }
    print(json.dumps(summary, indent=2))
    return 0 if report.status != MacroAgentStatus.NOT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
