"""EnergyCommodityAgent V1."""

from backend.agents.macro_common.engine import run_macro_agent


def run_energy_commodity(input_path, *, config_path=None, write_outputs: bool = True):
    return run_macro_agent(
        "EnergyCommodityAgent",
        input_path,
        config_path=config_path,
        write_outputs=write_outputs,
    )
