from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.agents.social_common.paths import SocialLoadError
from backend.agents.social_listening.agent import run_social_listening


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Social Listening Agent V1 — collect public consumer conversations (no fabricated posts)."
    )
    parser.add_argument("data_root", type=Path, help="Path to backend/data/")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=None,
        help="TEST fixture JSON (explicit TEST_FIXTURES_ONLY mode)",
    )
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_social_listening(
            args.data_root, fixture_path=args.fixtures, write_outputs=not args.no_write
        )
    except SocialLoadError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
