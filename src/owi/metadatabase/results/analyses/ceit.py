"""CEIT corrosion monitoring analysis."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ..models import AnalysisKind, PlotRequest, PlotResponse, RelatedObject, ResultScope, ResultSeries, ResultVector
from ..plotting.ceit import plot_ceit_analyses
from ..registry import register_analysis
from .base import BaseAnalysis

CORROSION_MONITORING_ANALYSIS_NAME = "CeitCorrosionMonitoring"
CEIT_METRICS: dict[str, tuple[str, str]] = {
    "temperature": ("temperatura", "degC"),
    "battery": ("bateria", "V"),
    "tof": ("Tof", "us"),
    "amplitude": ("Amplitude", "count"),
    "meas_gain": ("MeasGain", "gain"),
}


class CorrosionMonitoringRow(BaseModel):
    """Validated representation of one CEIT corrosion monitoring row."""

    model_config = ConfigDict(extra="forbid")

    date: str
    time: str
    sensor_identifier: str
    temperatura: float
    bateria: float
    tof: list[float] = Field(alias="Tof", min_length=1)
    amplitude: float = Field(alias="Amplitude")
    meas_gain: float = Field(alias="MeasGain")
    site_id: int | None = None
    location_id: int | None = None
    related_object: RelatedObject | None = None

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


class CorrosionMonitoringInput(BaseModel):
    """Validated input payload for corrosion monitoring analysis."""

    model_config = ConfigDict(extra="forbid")

    rows: list[CorrosionMonitoringRow] = Field(min_length=1)


def _sanitize_json_text(raw_text: str) -> str:
    """Remove trailing commas so lightly malformed CEIT exports can be parsed."""
    return re.sub(r",(\s*[}\]])", r"\1", raw_text)


def load_ceit_measurements(path: str | Path) -> list[CorrosionMonitoringRow]:
    """Load validated CEIT measurements from a JSON file."""
    payload = json.loads(_sanitize_json_text(Path(path).read_text(encoding="utf-8")))
    return [CorrosionMonitoringRow.model_validate(item) for item in payload]


def ceit_frame_from_measurements(measurements: Sequence[CorrosionMonitoringRow]) -> pd.DataFrame:
    """Convert CEIT measurements to a normalized long dataframe."""
    rows: list[dict[str, Any]] = []
    for measurement in measurements:
        related_object = measurement.related_object
        if isinstance(related_object, dict):
            related_object = RelatedObject(**related_object)
        for metric, value in measurement.metric_values().items():
            rows.append(
                {
                    "analysis_name": CORROSION_MONITORING_ANALYSIS_NAME,
                    "sensor_identifier": measurement.sensor_identifier,
                    "metric": metric,
                    "timestamp": measurement.timestamp.isoformat(),
                    "value": float(value),
                    "site_id": measurement.site_id,
                    "location_id": measurement.location_id,
                    "related_object_type": related_object.type if related_object is not None else None,
                    "related_object_id": related_object.id if related_object is not None else None,
                }
            )
    return pd.DataFrame(rows)


@register_analysis
class CorrosionMonitoring(BaseAnalysis):
    """Time-series analysis for CEIT corrosion monitoring measurements."""

    analysis_name = CORROSION_MONITORING_ANALYSIS_NAME
    analysis_kind = AnalysisKind.TIME_SERIES.value
    result_scope = ResultScope.LOCATION.value
    default_plot_type = "time_series"

    def validate_inputs(self, payload: Any) -> CorrosionMonitoringInput:
        """Validate corrosion monitoring request data."""
        if isinstance(payload, CorrosionMonitoringInput):
            return payload
        return CorrosionMonitoringInput.model_validate(payload)

    def compute(self, payload: Any) -> pd.DataFrame:
        """Normalize validated CEIT measurements into a long table."""
        validated = self.validate_inputs(payload)
        return ceit_frame_from_measurements(validated.rows)

    def to_results(self, payload: Any) -> list[ResultSeries]:
        """Convert corrosion monitoring rows to persisted result series."""
        validated = self.validate_inputs(payload)
        grouped: dict[
            tuple[str, int | None, int | None, str | None, int | None],
            list[CorrosionMonitoringRow],
        ] = {}
        for row in validated.rows:
            related_object = row.related_object
            if isinstance(related_object, dict):
                related_object = RelatedObject(**related_object)
            related_object_type = related_object.type if related_object is not None else None
            related_object_id = related_object.id if related_object is not None else None
            key = (
                row.sensor_identifier,
                row.site_id,
                row.location_id,
                related_object_type,
                related_object_id,
            )
            grouped.setdefault(key, []).append(row)

        results: list[ResultSeries] = []
        for (sensor_identifier, site_id, location_id, _, _), sensor_rows in sorted(grouped.items()):
            ordered_rows = sorted(sensor_rows, key=lambda item: item.timestamp)
            timestamps = [item.timestamp.timestamp() for item in ordered_rows]
            related_object = ordered_rows[0].related_object
            if isinstance(related_object, dict):
                related_object = RelatedObject(**related_object)
            for metric, (source_field, unit) in CEIT_METRICS.items():
                values = [item.metric_values()[metric] for item in ordered_rows]
                results.append(
                    ResultSeries(
                        analysis_name=self.analysis_name,
                        analysis_kind=AnalysisKind.TIME_SERIES,
                        result_scope=ResultScope.LOCATION if location_id is not None else ResultScope.SITE,
                        short_description=f"{sensor_identifier}:{metric}",
                        description=f"CEIT {metric} time series for sensor {sensor_identifier}.",
                        site_id=site_id,
                        location_id=location_id,
                        related_object=related_object,
                        data_additional={
                            "sensor_identifier": sensor_identifier,
                            "metric": metric,
                            "series_key": f"{sensor_identifier}:{metric}",
                            "source_field": source_field,
                            "related_object_type": related_object.type if related_object is not None else None,
                            "related_object_id": related_object.id if related_object is not None else None,
                        },
                        vectors=[
                            ResultVector(name="timestamp", unit="s", values=timestamps),
                            ResultVector(name=metric, unit=unit, values=values),
                        ],
                    )
                )
        return results

    def from_results(self, results: Sequence[ResultSeries]) -> pd.DataFrame:
        """Reconstruct normalized CEIT rows from stored results."""
        rows: list[dict[str, Any]] = []
        for result in results:
            sensor_identifier = str(result.data_additional.get("sensor_identifier", "unknown"))
            metric = str(result.data_additional.get("metric", result.vectors[1].name))
            related_object_type = result.data_additional.get(
                "related_object_type",
                result.related_object.type if result.related_object is not None else None,
            )
            related_object_id = result.data_additional.get(
                "related_object_id",
                result.related_object.id if result.related_object is not None else None,
            )
            point_count = min(len(result.vectors[0].values), len(result.vectors[1].values))
            for index in range(point_count):
                rows.append(
                    {
                        "analysis_name": result.analysis_name,
                        "sensor_identifier": sensor_identifier,
                        "metric": metric,
                        "timestamp": datetime.fromtimestamp(
                            result.vectors[0].values[index],
                            tz=timezone.utc,
                        ).isoformat(),
                        "value": float(result.vectors[1].values[index]),
                        "site_id": result.site_id,
                        "location_id": result.location_id,
                        "related_object_type": related_object_type,
                        "related_object_id": related_object_id,
                    }
                )
        return pd.DataFrame(rows)

    def plot(
        self,
        results: Sequence[ResultSeries],
        request: PlotRequest | None = None,
        plot_strategy: Any | None = None,
    ) -> PlotResponse:
        """Render corrosion monitoring results using the dedicated plot."""
        del request, plot_strategy
        return plot_ceit_analyses(self.from_results(results))


__all__ = [
    "CEIT_METRICS",
    "CORROSION_MONITORING_ANALYSIS_NAME",
    "CorrosionMonitoring",
    "CorrosionMonitoringInput",
    "CorrosionMonitoringRow",
    "_sanitize_json_text",
    "ceit_frame_from_measurements",
    "load_ceit_measurements",
]
