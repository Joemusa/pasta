"""JSON sanitisation for dashboard payloads. Never emit NaN or Infinity."""

from __future__ import annotations

from typing import Any


def json_safe(value: Any) -> Any:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item") and callable(getattr(value, "item", None)):
        try:
            return json_safe(value.item())
        except (ValueError, AttributeError, TypeError):
            return None
    return value
