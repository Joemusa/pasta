from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.consumer_sentiment.agent import run_consumer_sentiment
from backend.agents.social_common.paths import SocialLoadError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consumer Sentiment Agent V1 — conversation tone, not sales causality."
    )
    parser.add_argument("input", type=Path, help="Path to backend/data/")
    parser.add_argument("--fixtures", type=Path, default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_consumer_sentiment(
            args.input, fixture_path=args.fixtures, write_outputs=not args.no_write
        )
    except (SocialLoadError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report.to_json_dict(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
