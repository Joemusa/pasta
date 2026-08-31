"""CLI: python -m backend.agents.storytelling backend/data/"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.storytelling.agent import run_storytelling
from backend.agents.storytelling.loader import StorytellingLoadError
from backend.agents.storytelling.models import StorytellingStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Storytelling Engine V1: turn Commercial Brain one-slide JSON into a single executive "
            "FMCG story. Does not recalculate opportunities or claim guaranteed incremental sales."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Data root with brain_reports/, or a commercial_brain_v1_one_slide.json / *.brain.json file",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing storytelling_v1_one_slide.json (still prints the slide)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_storytelling(args.input, write_outputs=not args.no_write)
    except (StorytellingLoadError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report.one_slide.model_dump(mode="json"), indent=2))
    return 0 if report.status != StorytellingStatus.NOT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
