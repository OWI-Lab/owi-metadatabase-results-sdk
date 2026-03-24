"""CEIT sensor measurement models and data helpers."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

CEIT_ANALYSIS_PREFIX = "CEITSensor"
CEIT_METRICS: dict[str, tuple[str, str]] = {
    "temperature": ("temperatura", "degC"),
    "battery": ("bateria", "V"),
    "tof": ("Tof", "us"),
    "amplitude": ("Amplitude", "count"),
    "meas_gain": ("MeasGain", "gain"),
}


class CeitMeasurement(BaseModel):
    """Validated representation of one CEIT measurement row."""

    model_config = ConfigDict(extra="forbid")

    date: str
    time: str
    sensor_identifier: str
    temperatura: float
    bateria: float
    tof: list[float] = Field(alias="Tof", min_length=1)
    amplitude: float = Field(alias="Amplitude")
    meas_gain: float = Field(alias="MeasGain")

    @property
    def timestamp(self) -> datetime:
        """Return the measurement timestamp as UTC."""
        return datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    def metric_values(self) -> dict[str, float]:
        """Return the normalized metric payload for this measurement."""
        return {
            "temperature": float(self.temperatura),
            "battery": float(self.bateria),
            "tof": float(self.tof[0]),
            "amplitude": float(self.amplitude),
            "meas_gain": float(self.meas_gain),
        }


def _sanitize_json_text(raw_text: str) -> str:
    """Remove trailing commas so lightly malformed CEIT exports can be parsed."""
    return re.sub(r",(\s*[}\]])", r"\1", raw_text)


def load_ceit_measurements(path: str | Path) -> list[CeitMeasurement]:
    """Load validated CEIT measurements from a JSON file."""
    payload = json.loads(_sanitize_json_text(Path(path).read_text(encoding="utf-8")))
    return [CeitMeasurement.model_validate(item) for item in payload]


def ceit_frame_from_measurements(measurements: Sequence[CeitMeasurement]) -> pd.DataFrame:
    """Convert CEIT measurements to a normalized long dataframe."""
    rows: list[dict[str, Any]] = []
    for measurement in measurements:
        for metric, value in measurement.metric_values().items():
            rows.append(
                {
                    "sensor_identifier": measurement.sensor_identifier,
                    "timestamp": measurement.timestamp.isoformat(),
                    "metric": metric,
                    "value": float(value),
                }
            )
    return pd.DataFrame(rows)
