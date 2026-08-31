"""InflationCostAgent V1."""

from backend.agents.macro_common.engine import run_macro_agent


def run_inflation_cost(input_path, *, config_path=None, write_outputs: bool = True):
    return run_macro_agent(
        "InflationCostAgent",
        input_path,
        config_path=config_path,
        write_outputs=write_outputs,
    )
