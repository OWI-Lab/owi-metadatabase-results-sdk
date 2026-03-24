"""CEIT sensor results service for persisting and querying measurements."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..analyses.ceit import (
    CEIT_ANALYSIS_PREFIX,
    CEIT_METRICS,
    CeitMeasurement,
    load_ceit_measurements,
)
from ..io import ResultsAPI
from ..models import AnalysisDefinition, AnalysisKind, ResultScope, ResultSeries, ResultVector
from ..plotting.ceit import plot_ceit_analyses
from ..serializers import DjangoAnalysisSerializer, DjangoResultSerializer


class CeitResultsService:
    """Persist and plot CEIT measurements using the results backend."""

    def __init__(
        self,
        api: Any | None = None,
        *,
        model_definition_id: int = 0,
        location_id: int | None = None,
    ) -> None:
        self.api = api or ResultsAPI(token="dummy")
        self.model_definition_id = model_definition_id
        self.location_id = location_id
        self.analysis_serializer = DjangoAnalysisSerializer()
        self.result_serializer = DjangoResultSerializer()

    def analysis_name_for_sensor(self, sensor_identifier: str) -> str:
        """Return the analysis name used for one CEIT sensor."""
        return f"{CEIT_ANALYSIS_PREFIX}:{sensor_identifier}"

    def build_analysis_definition(self, sensor_identifier: str, source: str | None = None) -> AnalysisDefinition:
        """Create the analysis metadata used for one CEIT sensor."""
        return AnalysisDefinition(
            name=self.analysis_name_for_sensor(sensor_identifier),
            model_definition_id=self.model_definition_id,
            location_id=self.location_id,
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
                existing_rows = self.api.list_results(analysis=analysis_id, short_description=series.short_description)[
                    "data"
                ]
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
            sensor_identifier = str(
                series.data_additional.get("sensor_identifier", series.analysis_name.split(":")[-1])
            )
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
