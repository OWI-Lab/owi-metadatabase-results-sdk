"""Utility functions for the results SDK."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def summarize_payload(payload: Any) -> str:
    """Return a compact payload summary for debug logging."""
    if isinstance(payload, Mapping):
        return str(list(payload.keys()))
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return f"items={len(payload)}"
    return type(payload).__name__


def load_token_from_env_file(env_file: Path, env_var: str = "OWI_METADATABASE_API_TOKEN") -> str | None:
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{env_var}="):
            token = line.split("=", 1)[1].strip()
            return token or None
    return None
