"""CLI helpers for specialist macro agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.agents.macro_common.catalog import MacroLoadError
from backend.agents.macro_common.engine import run_macro_agent
from backend.agents.macro_common.models import MacroAgentStatus


def specialist_main(agent: str, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            f"{agent}: consume sourced South African macro observations. "
            "Does not recalculate POS opportunities or claim guaranteed incremental sales."
        )
    )
    parser.add_argument("input", type=Path, help="Data root with macro_observations/ (backend/data/)")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_macro_agent(agent, args.input, config_path=args.config, write_outputs=not args.no_write)
    except (MacroLoadError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report.to_json_dict(), indent=2))
    return 0 if report.status != MacroAgentStatus.NOT_READY else 1
