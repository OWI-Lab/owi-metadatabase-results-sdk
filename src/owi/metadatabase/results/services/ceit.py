"""CEIT sensor results service for persisting and querying measurements."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm.auto import tqdm

from ..analyses.ceit import (
    CEIT_ANALYSIS_PREFIX,
    CEIT_METRICS,
    CeitMeasurement,
    load_ceit_measurements,
)
from ..io import ResultsAPI
from ..models import (
    AnalysisDefinition,
    AnalysisKind,
    RelatedObject,
    ResultScope,
    ResultSeries,
    ResultVector,
)
from ..plotting.ceit import plot_ceit_analyses
from ..serializers import DjangoAnalysisSerializer, DjangoResultSerializer

CEIT_SHARED_ANALYSIS_NAME = "CeitCorrosionMonitoring"
SHM_SIGNAL_RELATED_OBJECT_TYPE = "shm.signal"


def _upload_progress(total: int, desc: str):
    """Return a tqdm progress bar for CEIT result uploads."""
    return tqdm(total=total, desc=desc, unit="series", disable=total == 0)


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

    @staticmethod
    def series_key_for_sensor_metric(sensor_identifier: str, metric: str) -> str:
        """Return a stable series identifier for one sensor metric pair."""
        return f"{sensor_identifier}:{metric}"

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

    def build_shared_analysis_definition(
        self,
        *,
        analysis_name: str = CEIT_SHARED_ANALYSIS_NAME,
        source: str | None = None,
    ) -> AnalysisDefinition:
        """Create the shared CEIT corrosion monitoring analysis definition."""
        return AnalysisDefinition(
            name=analysis_name,
            model_definition_id=self.model_definition_id,
            location_id=self.location_id,
            source_type="ceit-json",
            source=source,
            description="Shared CEIT corrosion monitoring analysis across sensors.",
            additional_data={"analysis_family": CEIT_ANALYSIS_PREFIX, "shared_analysis": True},
        )

    def build_sensor_results(
        self,
        sensor_identifier: str,
        measurements: Sequence[CeitMeasurement],
        *,
        site_id: int | None = None,
        location_id: int | None = None,
        analysis_name: str | None = None,
        use_stable_series_keys: bool = False,
        signal_id: int | None = None,
        signal_history: Mapping[str, Any] | None = None,
        additional_data: Mapping[str, Any] | None = None,
    ) -> list[ResultSeries]:
        """Convert measurements for a sensor into appendable result rows."""
        resolved_analysis_name = analysis_name or self.analysis_name_for_sensor(sensor_identifier)
        ordered_measurements = sorted(measurements, key=lambda item: item.timestamp)
        timestamps = [item.timestamp.timestamp() for item in ordered_measurements]
        result_scope = ResultScope.LOCATION if location_id is not None else ResultScope.SITE
        results: list[ResultSeries] = []
        for metric, (source_field, unit) in CEIT_METRICS.items():
            values = [item.metric_values()[metric] for item in ordered_measurements]
            series_key = self.series_key_for_sensor_metric(sensor_identifier, metric)
            metric_additional_data: dict[str, Any] = {
                "analysis_name": resolved_analysis_name,
                "sensor_identifier": sensor_identifier,
                "metric": metric,
                "source_field": source_field,
                "series_key": series_key,
            }
            if signal_id is not None:
                metric_additional_data["signal_id"] = int(signal_id)
            if signal_history is not None:
                metric_additional_data["signal_history"] = dict(signal_history)
            if additional_data is not None:
                metric_additional_data.update(dict(additional_data))
            results.append(
                ResultSeries(
                    analysis_name=resolved_analysis_name,
                    analysis_kind=AnalysisKind.TIME_SERIES,
                    result_scope=result_scope,
                    short_description=series_key if use_stable_series_keys else metric,
                    description=f"CEIT {metric} time series for sensor {sensor_identifier}.",
                    site_id=site_id,
                    location_id=location_id,
                    related_object=(
                        RelatedObject(type=SHM_SIGNAL_RELATED_OBJECT_TYPE, id=int(signal_id))
                        if signal_id is not None
                        else None
                    ),
                    data_additional=metric_additional_data,
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

    def _ensure_analysis_definition(self, definition: AnalysisDefinition) -> tuple[int, bool]:
        analyses_frame = self.api.list_analyses(name=definition.name)["data"]
        if not analyses_frame.empty:
            return int(analyses_frame.iloc[0]["id"]), False
        payload = self.analysis_serializer.to_payload(definition)
        created = self.api.create_analysis(payload)
        if created["id"] is None:
            raise ValueError(f"Analysis creation did not return an id for analysis {definition.name}.")
        return int(created["id"]), True

    def _ensure_analysis(self, sensor_identifier: str, source: str | None = None) -> tuple[int, bool]:
        definition = self.build_analysis_definition(sensor_identifier, source=source)
        return self._ensure_analysis_definition(definition)

    def ensure_shared_analysis(
        self,
        *,
        analysis_name: str = CEIT_SHARED_ANALYSIS_NAME,
        source: str | None = None,
    ) -> tuple[int, bool]:
        """Create or reuse the shared CEIT corrosion analysis."""
        definition = self.build_shared_analysis_definition(analysis_name=analysis_name, source=source)
        return self._ensure_analysis_definition(definition)

    def _upsert_result_series(
        self,
        *,
        analysis_id: int,
        analysis_created: bool,
        sensor_identifier: str,
        series: ResultSeries,
    ) -> dict[str, Any]:
        existing_rows = self.api.list_results(analysis=analysis_id, short_description=series.short_description)["data"]
        if len(existing_rows) > 1:
            raise ValueError(
                "Multiple persisted rows found for one CEIT series key "
                f"{series.short_description!r} in analysis {analysis_id}."
            )
        if existing_rows.empty:
            payload = self.result_serializer.to_payload(series, analysis_id=analysis_id)
            created = self.api.create_result(payload)
            return {
                "sensor_identifier": sensor_identifier,
                "metric": str(series.data_additional.get("metric", series.short_description)),
                "series_key": series.short_description,
                "analysis_created": analysis_created,
                "action": "created",
                "result_id": created["id"],
                "appended_points": len(series.vectors[0].values),
                "signal_id": series.data_additional.get("signal_id"),
            }

        existing_row = existing_rows.to_dict(orient="records")[0]
        existing_series = self.result_serializer.from_mapping(existing_row)
        merged_series, appended_points = self._merge_result_series(existing_series, series)
        if appended_points == 0:
            return {
                "sensor_identifier": sensor_identifier,
                "metric": str(series.data_additional.get("metric", series.short_description)),
                "series_key": series.short_description,
                "analysis_created": analysis_created,
                "action": "unchanged",
                "result_id": int(existing_row["id"]),
                "appended_points": 0,
                "signal_id": series.data_additional.get("signal_id"),
            }

        payload = self.result_serializer.to_payload(merged_series, analysis_id=analysis_id)
        updated = self.api.update_result(int(existing_row["id"]), payload)
        return {
            "sensor_identifier": sensor_identifier,
            "metric": str(series.data_additional.get("metric", series.short_description)),
            "series_key": series.short_description,
            "analysis_created": analysis_created,
            "action": "patched",
            "result_id": updated["id"],
            "appended_points": appended_points,
            "signal_id": series.data_additional.get("signal_id"),
        }

    def _merge_result_series(self, existing: ResultSeries, incoming: ResultSeries) -> tuple[ResultSeries, int]:
        existing_points = {
            existing.vectors[0].values[index]: existing.vectors[1].values[index]
            for index in range(min(len(existing.vectors[0].values), len(existing.vectors[1].values)))
        }
        appended_points = 0
        incoming_point_count = min(len(incoming.vectors[0].values), len(incoming.vectors[1].values))
        for index in range(incoming_point_count):
            timestamp = incoming.vectors[0].values[index]
            value = incoming.vectors[1].values[index]
            if timestamp not in existing_points:
                appended_points += 1
            existing_points[timestamp] = value
        ordered_pairs = sorted(existing_points.items(), key=lambda item: item[0])
        merged_series = existing.model_copy(
            update={
                "site_id": incoming.site_id if incoming.site_id is not None else existing.site_id,
                "location_id": incoming.location_id if incoming.location_id is not None else existing.location_id,
                "description": incoming.description or existing.description,
                "related_object": incoming.related_object or existing.related_object,
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
        total_series = len(grouped) * len(CEIT_METRICS)
        with _upload_progress(total_series, "Uploading CEIT result series") as progress:
            for sensor_identifier, sensor_measurements in sorted(grouped.items()):
                analysis_id, analysis_created = self._ensure_analysis(sensor_identifier, source=str(path))
                for series in self.build_sensor_results(sensor_identifier, sensor_measurements, site_id=site_id):
                    summary.append(
                        self._upsert_result_series(
                            analysis_id=analysis_id,
                            analysis_created=analysis_created,
                            sensor_identifier=sensor_identifier,
                            series=series,
                        )
                    )
                    progress.update(1)
        return summary

    def upsert_measurements_to_shared_analysis(
        self,
        path: str | Path,
        *,
        site_id: int | None = None,
        location_id: int | None = None,
        analysis_name: str = CEIT_SHARED_ANALYSIS_NAME,
        signal_ids_by_sensor: Mapping[str, int] | None = None,
        signal_history_by_sensor: Mapping[str, Mapping[str, Any]] | None = None,
        additional_data_by_sensor: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Upsert CEIT measurements into one shared analysis across sensors."""
        measurements = self.load_measurements(path)
        grouped: dict[str, list[CeitMeasurement]] = defaultdict(list)
        for measurement in measurements:
            grouped[measurement.sensor_identifier].append(measurement)

        analysis_id, analysis_created = self.ensure_shared_analysis(analysis_name=analysis_name, source=str(path))
        summary: list[dict[str, Any]] = []
        total_series = len(grouped) * len(CEIT_METRICS)
        with _upload_progress(total_series, "Uploading shared CEIT result series") as progress:
            for sensor_identifier, sensor_measurements in sorted(grouped.items()):
                signal_id = None if signal_ids_by_sensor is None else signal_ids_by_sensor.get(sensor_identifier)
                signal_history = (
                    None if signal_history_by_sensor is None else signal_history_by_sensor.get(sensor_identifier)
                )
                sensor_additional_data = (
                    None if additional_data_by_sensor is None else additional_data_by_sensor.get(sensor_identifier)
                )
                for series in self.build_sensor_results(
                    sensor_identifier,
                    sensor_measurements,
                    site_id=site_id,
                    location_id=location_id,
                    analysis_name=analysis_name,
                    use_stable_series_keys=True,
                    signal_id=signal_id,
                    signal_history=signal_history,
                    additional_data=sensor_additional_data,
                ):
                    summary.append(
                        self._upsert_result_series(
                            analysis_id=analysis_id,
                            analysis_created=analysis_created,
                            sensor_identifier=sensor_identifier,
                            series=series,
                        )
                    )
                    progress.update(1)

        return {
            "analysis_id": analysis_id,
            "analysis_name": analysis_name,
            "analysis_created": analysis_created,
            "summary": summary,
        }

    def frame_from_series(self, series_rows: Sequence[ResultSeries]) -> pd.DataFrame:
        """Convert persisted CEIT result series into a normalized long dataframe."""
        rows: list[dict[str, Any]] = []
        for series in series_rows:
            sensor_identifier = str(series.data_additional.get("sensor_identifier", "unknown"))
            metric = str(series.data_additional.get("metric", series.short_description))
            signal_id = series.data_additional.get("signal_id")
            point_count = min(len(series.vectors[0].values), len(series.vectors[1].values))
            for index in range(point_count):
                timestamp = series.vectors[0].values[index]
                value = series.vectors[1].values[index]
                rows.append(
                    {
                        "analysis_name": series.analysis_name,
                        "short_description": series.short_description,
                        "sensor_identifier": sensor_identifier,
                        "metric": metric,
                        "signal_id": signal_id,
                        "timestamp": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                        "value": float(value),
                    }
                )
        return pd.DataFrame(rows)

    def load_backend_series(self, **filters: Any) -> list[ResultSeries]:
        """Load CEIT result rows from the backend and deserialize them."""
        raw_frame = self.api.list_results(**filters)["data"]
        return [self.result_serializer.from_mapping(row) for row in raw_frame.to_dict(orient="records")]

    def load_backend_frame(self, sensor_identifiers: Sequence[str] | None = None) -> pd.DataFrame:
        """Load CEIT measurements back from persisted results."""
        filters: dict[str, Any] = {"analysis__name__startswith": f"{CEIT_ANALYSIS_PREFIX}:"}
        if sensor_identifiers:
            filters["analysis__name__in"] = [self.analysis_name_for_sensor(sensor) for sensor in sensor_identifiers]
        return self.frame_from_series(self.load_backend_series(**filters))

    def load_shared_backend_frame(
        self,
        *,
        analysis_id: int | None = None,
        analysis_name: str = CEIT_SHARED_ANALYSIS_NAME,
        sensor_identifiers: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Load the normalized dataframe for the shared CEIT corrosion analysis."""
        filters: dict[str, Any] = (
            {"analysis": analysis_id} if analysis_id is not None else {"analysis__name": analysis_name}
        )
        frame = self.frame_from_series(self.load_backend_series(**filters))
        if sensor_identifiers is None or frame.empty:
            return frame
        mask = frame["sensor_identifier"].isin(list(sensor_identifiers))
        filtered = frame.loc[mask, :].reset_index(drop=True)
        return filtered

    def plot_ceit_analyses(self, sensor_identifiers: Sequence[str] | None = None) -> Any:
        """Plot persisted CEIT measurements with a sensor dropdown."""
        return plot_ceit_analyses(self.load_backend_frame(sensor_identifiers))

    def plot_shared_analysis(
        self,
        *,
        analysis_id: int | None = None,
        analysis_name: str = CEIT_SHARED_ANALYSIS_NAME,
        sensor_identifiers: Sequence[str] | None = None,
    ) -> Any:
        """Plot the shared CEIT corrosion analysis with a sensor dropdown."""
        return plot_ceit_analyses(
            self.load_shared_backend_frame(
                analysis_id=analysis_id,
                analysis_name=analysis_name,
                sensor_identifiers=sensor_identifiers,
            )
        )
