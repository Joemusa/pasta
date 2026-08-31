from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.agents.social_brain.agent import run_social_brain
from backend.agents.social_common.paths import SocialLoadError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "SocialContextBrain V1: attach social intelligence as supporting consumer context. "
            "Does not recalculate POS opportunities or create commercial actions."
        )
    )
    parser.add_argument("input", type=Path, help="Data root with brain_reports/")
    parser.add_argument("--fixtures", type=Path, default=None, help="Labeled TEST fixture JSON")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_social_brain(
            args.input,
            fixture_path=args.fixtures,
            config_path=args.config,
            write_outputs=not args.no_write,
        )
    except (SocialLoadError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    summary = {
        "agent": report.agent,
        "status": report.status,
        "data_mode": report.data_mode,
        "verdict": report.verdict,
        "pos_story": report.pos_story.model_dump(mode="json"),
        "consumer_context": report.consumer_context,
        "emerging_risks": report.emerging_risks,
        "sources": report.sources,
        "report_output_path": report.report_output_path,
        "causality_claim": report.causality_claim,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
