"""Utility functions for the results SDK."""

from collections.abc import Mapping, Sequence
from typing import Any


def summarize_payload(payload: Any) -> str:
    """Return a compact payload summary for debug logging."""
    if isinstance(payload, Mapping):
        return str(list(payload.keys()))
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return f"items={len(payload)}"
    return type(payload).__name__
