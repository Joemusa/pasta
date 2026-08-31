"""ConsumerRetailAgent V1. Retains the existing FNB/BER CCI = -19 signal."""

from backend.agents.macro_common.engine import run_macro_agent


def run_consumer_retail(input_path, *, config_path=None, write_outputs: bool = True):
    return run_macro_agent(
        "ConsumerRetailAgent",
        input_path,
        config_path=config_path,
        write_outputs=write_outputs,
    )
