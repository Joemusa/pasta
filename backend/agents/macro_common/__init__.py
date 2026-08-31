"""Shared macro-specialist machinery. Does not modify POS agents or Storytelling Engine V1."""

from backend.agents.macro_common.catalog import MacroLoadError
from backend.agents.macro_common.engine import run_macro_agent
from backend.agents.macro_common.models import MACRO_COMMON_VERSION, MacroAgentStatus

__all__ = [
    "MACRO_COMMON_VERSION",
    "MacroAgentStatus",
    "MacroLoadError",
    "run_macro_agent",
]
