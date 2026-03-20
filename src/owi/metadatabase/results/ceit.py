"""Helpers for ingesting and plotting CEIT sensor measurements."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from pyecharts import options as opts
from pyecharts.charts import Line

from .io import ResultsAPI
from .models import AnalysisKind, AnalysisDefinition, ResultScope, ResultSeries, ResultVector
from .plotting import (
    _apply_cartesian_layout,
    _label_opts,
    _legend_opts,
    _title_opts,
    _tooltip_opts,
    _xaxis_opts,
    _yaxis_opts,
    build_dropdown_plot_response,
)
from .serializers import DjangoAnalysisSerializer, DjangoResultSerializer

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


def plot_ceit_analyses(data: pd.DataFrame | Sequence[CeitMeasurement]) -> Any:
    """Plot CEIT sensor measurements with a dropdown that switches sensors."""
    frame = ceit_frame_from_measurements(data) if not isinstance(data, pd.DataFrame) else data.copy()
    if frame.empty:
        raise ValueError("No CEIT measurements are available to plot.")
    charts: dict[str, Line] = {}
    for sensor_identifier, sensor_frame in frame.groupby("sensor_identifier"):
        chart = Line(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = list(dict.fromkeys(sensor_frame["timestamp"].astype(str).tolist()))
        chart.add_xaxis(x_values)
        for metric, metric_frame in sensor_frame.groupby("metric"):
            values_by_timestamp = dict(zip(metric_frame["timestamp"].astype(str), metric_frame["value"], strict=False))
            chart.add_yaxis(
                str(metric),
                cast(Any, [values_by_timestamp.get(timestamp) for timestamp in x_values]),
                is_smooth=False,
                is_symbol_show=True,
                symbol_size=6,
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(f"CEIT Sensor {sensor_identifier}"),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="axis"),
            xaxis_opts=_xaxis_opts(name="Timestamp", boundary_gap=False),
            yaxis_opts=_yaxis_opts(name="Value"),
        )
        _apply_cartesian_layout(chart)
        charts[str(sensor_identifier)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Sensor")


class CeitResultsService:
    """Persist and plot CEIT measurements using the results backend."""

    def __init__(self, api: Any | None = None) -> None:
        self.api = api or ResultsAPI(token="dummy")
        self.analysis_serializer = DjangoAnalysisSerializer()
        self.result_serializer = DjangoResultSerializer()

    def analysis_name_for_sensor(self, sensor_identifier: str) -> str:
        """Return the analysis name used for one CEIT sensor."""
        return f"{CEIT_ANALYSIS_PREFIX}:{sensor_identifier}"

    def build_analysis_definition(self, sensor_identifier: str, source: str | None = None) -> AnalysisDefinition:
        """Create the analysis metadata used for one CEIT sensor."""
        return AnalysisDefinition(
            name=self.analysis_name_for_sensor(sensor_identifier),
            source_type="ceit-json",
            source=source,
            description=f"CEIT measurement analysis for sensor {sensor_identifier}.",
            additional_data={"sensor_identifier": sensor_identifier, "analysis_family": CEIT_ANALYSIS_PREFIX},
        )

    def build_sensor_results(
        self,
        sensor_identifier: str,
        measurements: Sequence[CeitMeasurement],
        *,
        site_id: int | None = None,
    ) -> list[ResultSeries]:
        """Convert measurements for a sensor into appendable result rows."""
        analysis_name = self.analysis_name_for_sensor(sensor_identifier)
        ordered_measurements = sorted(measurements, key=lambda item: item.timestamp)
        timestamps = [item.timestamp.timestamp() for item in ordered_measurements]
        results: list[ResultSeries] = []
        for metric, (source_field, unit) in CEIT_METRICS.items():
            values = [item.metric_values()[metric] for item in ordered_measurements]
            results.append(
                ResultSeries(
                    analysis_name=analysis_name,
                    analysis_kind=AnalysisKind.TIME_SERIES,
                    result_scope=ResultScope.SITE,
                    short_description=metric,
                    description=f"CEIT {metric} time series for sensor {sensor_identifier}.",
                    site_id=site_id,
                    data_additional={
                        "sensor_identifier": sensor_identifier,
                        "metric": metric,
                        "source_field": source_field,
                        "series_key": f"{sensor_identifier}:{metric}",
                    },
                    vectors=[
                        ResultVector(name="timestamp", unit="s", values=timestamps),
                        ResultVector(name=metric, unit=unit, values=values),
                    ],
                )
            )
        return results

    def load_measurements(self, path: str | Path) -> list[CeitMeasurement]:
        """Load validated CEIT measurements from disk."""
        return load_ceit_measurements(path)

    def _ensure_analysis(self, sensor_identifier: str, source: str | None = None) -> tuple[int, bool]:
        analysis_name = self.analysis_name_for_sensor(sensor_identifier)
        analyses_frame = self.api.list_analyses(name=analysis_name)["data"]
        if not analyses_frame.empty:
            return int(analyses_frame.iloc[0]["id"]), False
        payload = self.analysis_serializer.to_payload(self.build_analysis_definition(sensor_identifier, source=source))
        created = self.api.create_analysis(payload)
        if created["id"] is None:
            raise ValueError(f"Analysis creation did not return an id for sensor {sensor_identifier}.")
        return int(created["id"]), True

    def _merge_result_series(self, existing: ResultSeries, incoming: ResultSeries) -> tuple[ResultSeries, int]:
        existing_points = dict(zip(existing.vectors[0].values, existing.vectors[1].values, strict=False))
        appended_points = 0
        for timestamp, value in zip(incoming.vectors[0].values, incoming.vectors[1].values, strict=False):
            if timestamp not in existing_points:
                appended_points += 1
            existing_points[timestamp] = value
        ordered_pairs = sorted(existing_points.items(), key=lambda item: item[0])
        merged_series = existing.model_copy(
            update={
                "site_id": incoming.site_id if incoming.site_id is not None else existing.site_id,
                "description": incoming.description or existing.description,
                "data_additional": {**existing.data_additional, **incoming.data_additional},
                "vectors": [
                    ResultVector(
                        name=existing.vectors[0].name,
                        unit=existing.vectors[0].unit,
                        values=[float(timestamp) for timestamp, _ in ordered_pairs],
                    ),
                    ResultVector(
                        name=existing.vectors[1].name,
                        unit=existing.vectors[1].unit,
                        values=[float(value) for _, value in ordered_pairs],
                    ),
                ],
            }
        )
        return merged_series, appended_points

    def upsert_measurements(self, path: str | Path, *, site_id: int | None = None) -> list[dict[str, Any]]:
        """Create analyses as needed and append new CEIT measurements to existing results."""
        measurements = self.load_measurements(path)
        grouped: dict[str, list[CeitMeasurement]] = defaultdict(list)
        for measurement in measurements:
            grouped[measurement.sensor_identifier].append(measurement)

        summary: list[dict[str, Any]] = []
        for sensor_identifier, sensor_measurements in sorted(grouped.items()):
            analysis_id, analysis_created = self._ensure_analysis(sensor_identifier, source=str(path))
            for series in self.build_sensor_results(sensor_identifier, sensor_measurements, site_id=site_id):
                existing_rows = self.api.list_results(analysis=analysis_id, short_description=series.short_description)["data"]
                if existing_rows.empty:
                    payload = self.result_serializer.to_payload(series, analysis_id=analysis_id)
                    created = self.api.create_result(payload)
                    summary.append(
                        {
                            "sensor_identifier": sensor_identifier,
                            "metric": series.short_description,
                            "analysis_created": analysis_created,
                            "action": "created",
                            "result_id": created["id"],
                            "appended_points": len(series.vectors[0].values),
                        }
                    )
                    continue

                existing_row = existing_rows.to_dict(orient="records")[0]
                existing_series = self.result_serializer.from_mapping(existing_row)
                merged_series, appended_points = self._merge_result_series(existing_series, series)
                if appended_points == 0:
                    summary.append(
                        {
                            "sensor_identifier": sensor_identifier,
                            "metric": series.short_description,
                            "analysis_created": analysis_created,
                            "action": "unchanged",
                            "result_id": int(existing_row["id"]),
                            "appended_points": 0,
                        }
                    )
                    continue
                payload = self.result_serializer.to_payload(merged_series, analysis_id=analysis_id)
                updated = self.api.update_result(int(existing_row["id"]), payload)
                summary.append(
                    {
                        "sensor_identifier": sensor_identifier,
                        "metric": series.short_description,
                        "analysis_created": analysis_created,
                        "action": "patched",
                        "result_id": updated["id"],
                        "appended_points": appended_points,
                    }
                )
        return summary

    def load_backend_frame(self, sensor_identifiers: Sequence[str] | None = None) -> pd.DataFrame:
        """Load CEIT measurements back from persisted results."""
        filters: dict[str, Any] = {"analysis__name__startswith": f"{CEIT_ANALYSIS_PREFIX}:"}
        if sensor_identifiers:
            filters["analysis__name__in"] = [self.analysis_name_for_sensor(sensor) for sensor in sensor_identifiers]
        raw_frame = self.api.list_results(**filters)["data"]
        rows: list[dict[str, Any]] = []
        for mapping in raw_frame.to_dict(orient="records"):
            series = self.result_serializer.from_mapping(mapping)
            sensor_identifier = str(series.data_additional.get("sensor_identifier", series.analysis_name.split(":")[-1]))
            metric = str(series.data_additional.get("metric", series.short_description))
            for timestamp, value in zip(series.vectors[0].values, series.vectors[1].values, strict=False):
                rows.append(
                    {
                        "sensor_identifier": sensor_identifier,
                        "timestamp": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                        "metric": metric,
                        "value": float(value),
                    }
                )
        return pd.DataFrame(rows)

    def plot_ceit_analyses(self, sensor_identifiers: Sequence[str] | None = None) -> Any:
        """Plot persisted CEIT measurements with a sensor dropdown."""
        return plot_ceit_analyses(self.load_backend_frame(sensor_identifiers))