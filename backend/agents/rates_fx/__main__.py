"""CLI: python -m backend.agents.rates_fx backend/data/"""

from __future__ import annotations

import sys

from backend.agents.macro_common.cli import specialist_main


def main(argv: list[str] | None = None) -> int:
    return specialist_main("RatesFXAgent", argv)


if __name__ == "__main__":
    sys.exit(main())
