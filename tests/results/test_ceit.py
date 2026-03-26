"""Tests for CEIT ingestion helpers and custom dropdown plots."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from owi.metadatabase.results import (
    CeitResultsService,
    load_ceit_measurements,
    plot_ceit_analyses,
    plot_lifetime_design_frequencies_by_location,
    plot_lifetime_design_frequencies_geo,
)
from owi.metadatabase.results.analyses.ceit import (
    CEIT_ANALYSIS_PREFIX,
    CEIT_METRICS,
    CeitMeasurement,
    _sanitize_json_text,
    ceit_frame_from_measurements,
)


class ProgressBarRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def factory(self, *args: object, **kwargs: object):
        updates: list[int] = []
        call: dict[str, object] = {"args": args, "kwargs": kwargs, "updates": updates}
        self.calls.append(call)

        class _ProgressBar:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb) -> bool:
                return False

            def update(self_inner, amount: int) -> None:
                updates.append(amount)

        return _ProgressBar()


class StubCeitApi:
    """Small API stub used to validate CEIT upsert behavior."""

    def __init__(self) -> None:
        self.created_analyses: list[dict[str, object]] = []
        self.created_results: list[dict[str, object]] = []
        self.updated_results: list[tuple[int, dict[str, object]]] = []
        self.result_rows = pd.DataFrame(
            [
                {
                    "id": 101,
                    "analysis": 1,
                    "site": 77,
                    "location": None,
                    "name_col1": "timestamp",
                    "units_col1": "s",
                    "value_col1": [1_741_781_112.0],
                    "name_col2": "temperature",
                    "units_col2": "degC",
                    "value_col2": [10.0],
                    "short_description": "temperature",
                    "description": "Existing series",
                    "data_additional": {
                        "analysis_name": "CEITSensor:DA8F",
                        "analysis_kind": "time_series",
                        "result_scope": "site",
                        "sensor_identifier": "DA8F",
                        "metric": "temperature",
                    },
                }
            ]
        )

    def list_analyses(self, name: str | None = None, **kwargs: object) -> dict[str, pd.DataFrame]:
        return {"data": pd.DataFrame([{"id": 1, "name": name or "CEITSensor:DA8F"}])}

    def create_analysis(self, payload: dict[str, object]) -> dict[str, object]:
        self.created_analyses.append(payload)
        return {"id": 1, "data": pd.DataFrame([payload])}

    def list_results(self, **kwargs: object) -> dict[str, pd.DataFrame]:
        short_description = kwargs.get("short_description")
        if short_description == "temperature":
            return {"data": self.result_rows.copy()}
        return {"data": pd.DataFrame()}

    def create_result(self, payload: dict[str, object]) -> dict[str, object]:
        self.created_results.append(payload)
        return {"id": len(self.created_results) + 200, "data": pd.DataFrame([payload])}

    def update_result(self, result_id: int, payload: dict[str, object]) -> dict[str, object]:
        self.updated_results.append((result_id, payload))
        return {"id": result_id, "data": pd.DataFrame([payload])}


class SharedAnalysisStubCeitApi(StubCeitApi):
    """Small API stub used to validate shared-analysis CEIT behavior."""

    def __init__(self) -> None:
        super().__init__()
        self.result_rows = pd.DataFrame(
            [
                {
                    "id": 501,
                    "analysis": 55,
                    "site": 77,
                    "location": 88,
                    "name_col1": "timestamp",
                    "units_col1": "s",
                    "value_col1": [1_741_781_112.0],
                    "name_col2": "temperature",
                    "units_col2": "degC",
                    "value_col2": [10.0],
                    "short_description": "DA8F:temperature",
                    "description": "Existing shared series",
                    "related_object": {"type": "shm.signal", "id": 901},
                    "data_additional": {
                        "analysis_name": "CeitCorrosionMonitoring",
                        "analysis_kind": "time_series",
                        "result_scope": "location",
                        "sensor_identifier": "DA8F",
                        "metric": "temperature",
                        "signal_id": 901,
                    },
                }
            ]
        )

    def list_analyses(self, name: str | None = None, **kwargs: object) -> dict[str, pd.DataFrame]:
        return {"data": pd.DataFrame([{"id": 55, "name": name or "CeitCorrosionMonitoring"}])}

    def list_results(self, **kwargs: object) -> dict[str, pd.DataFrame]:
        if kwargs.get("analysis") == 55 or kwargs.get("analysis__id") == 55:
            rows = [
                self.result_rows.to_dict(orient="records")[0],
                *self.created_results,
                *[payload for _, payload in self.updated_results],
            ]
            frame = pd.DataFrame(rows)
            short_description = kwargs.get("short_description")
            if short_description is not None and not frame.empty:
                mask = frame["short_description"] == short_description
                frame = frame.loc[mask, :].reset_index(drop=True)
            return {"data": frame}
        return {"data": pd.DataFrame()}


def test_load_ceit_measurements_sanitizes_trailing_commas(tmp_path: Path) -> None:
    payload = tmp_path / "meas.json"
    payload.write_text(
        '[{"date":"2026-03-12","time":"12:05:12","sensor_identifier":"DA8F","temperatura":1.0,'
        '"bateria":2.0,"Tof":[3.0],"Amplitude":4.0,"MeasGain":5.0,},]',
        encoding="utf-8",
    )
    measurements = load_ceit_measurements(payload)
    assert len(measurements) == 1
    assert measurements[0].sensor_identifier == "DA8F"
    assert measurements[0].metric_values()["tof"] == 3.0


def test_ceit_upsert_measurements_patches_existing_and_creates_missing(tmp_path: Path) -> None:
    payload = tmp_path / "meas.json"
    payload.write_text(
        """
        [
            {
                "date": "2025-03-12",
                "time": "12:05:12",
                "sensor_identifier": "DA8F",
                "temperatura": 10.0,
                "bateria": 2.0,
                "Tof": [3.0],
                "Amplitude": 4.0,
                "MeasGain": 5.0
            },
            {
                "date": "2025-03-12",
                "time": "12:06:12",
                "sensor_identifier": "DA8F",
                "temperatura": 11.0,
                "bateria": 2.1,
                "Tof": [3.1],
                "Amplitude": 4.1,
                "MeasGain": 5.1
            }
        ]
        """,
        encoding="utf-8",
    )
    api = StubCeitApi()
    service = CeitResultsService(api=api)
    summary = service.upsert_measurements(payload, site_id=77)
    assert any(row["action"] == "patched" and row["metric"] == "temperature" for row in summary)
    assert any(row["action"] == "created" and row["metric"] == "battery" for row in summary)
    assert api.updated_results
    patched_payload = api.updated_results[0][1]
    assert patched_payload["value_col1"] == [1741781112.0, 1741781172.0]
    assert patched_payload["value_col2"] == [10.0, 11.0]


def test_ceit_upsert_measurements_uses_progress_bar(tmp_path: Path) -> None:
    payload = tmp_path / "meas.json"
    payload.write_text(
        """
        [
            {
                "date": "2025-03-12",
                "time": "12:05:12",
                "sensor_identifier": "DA8F",
                "temperatura": 10.0,
                "bateria": 2.0,
                "Tof": [3.0],
                "Amplitude": 4.0,
                "MeasGain": 5.0
            }
        ]
        """,
        encoding="utf-8",
    )
    api = StubCeitApi()
    service = CeitResultsService(api=api)
    progress = ProgressBarRecorder()

    with patch("owi.metadatabase.results.services.ceit.tqdm", new=progress.factory):
        service.upsert_measurements(payload, site_id=77)

    assert len(progress.calls) == 1
    assert progress.calls[0]["kwargs"] == {
        "total": len(CEIT_METRICS),
        "desc": "Uploading CEIT result series",
        "unit": "series",
        "disable": False,
    }
    assert progress.calls[0]["updates"] == [1] * len(CEIT_METRICS)


def test_plot_ceit_analyses_contains_sensor_dropdown() -> None:
    frame = pd.DataFrame(
        [
            {
                "sensor_identifier": "DA8F",
                "timestamp": "2025-03-12T12:05:12+00:00",
                "metric": "temperature",
                "value": 1.0,
            },
            {"sensor_identifier": "DA8F", "timestamp": "2025-03-12T12:06:12+00:00", "metric": "battery", "value": 2.0},
            {
                "sensor_identifier": "DA9D",
                "timestamp": "2025-03-12T12:05:12+00:00",
                "metric": "temperature",
                "value": 3.0,
            },
        ]
    )
    response = plot_ceit_analyses(frame)
    options_by_sensor = json.loads(response.json_options)
    assert "Sensor" in response.html
    assert "DA8F" in response.html
    assert "DA9D" in response.html
    assert "font-family:monospace" in response.html
    assert options_by_sensor["DA8F"]["textStyle"]["fontFamily"] == "monospace"
    assert options_by_sensor["DA8F"]["title"][0]["top"] != options_by_sensor["DA8F"]["legend"][0]["top"]


def test_frequency_dropdown_plots_include_metric_and_reference_options() -> None:
    frame = pd.DataFrame(
        [
            {"location_id": 1, "turbine": "A01", "metric": "FA1", "reference": "INFL", "y": 0.34},
            {"location_id": 1, "turbine": "A01", "metric": "FA1", "reference": "ACTU", "y": 0.33},
            {"location_id": 1, "turbine": "A01", "metric": "SS1", "reference": "INFL", "y": 0.35},
            {"location_id": 1, "turbine": "A01", "metric": "SS1", "reference": "ACTU", "y": 0.34},
            {"location_id": 2, "turbine": "A02", "metric": "FA1", "reference": "ACTU", "y": 0.31},
            {"location_id": 2, "turbine": "A02", "metric": "FA1", "reference": "INFL", "y": 0.32},
            {"location_id": 2, "turbine": "A02", "metric": "SS1", "reference": "ACTU", "y": 0.32},
            {"location_id": 2, "turbine": "A02", "metric": "SS1", "reference": "INFL", "y": 0.33},
        ]
    )
    location_frame = pd.DataFrame(
        [
            {"id": 1, "title": "A01", "northing": 51.5, "easting": 2.8},
            {"id": 2, "title": "A02", "northing": 51.6, "easting": 2.9},
        ]
    )
    scatter_response = plot_lifetime_design_frequencies_by_location(frame, location_frame=location_frame)
    geo_response = plot_lifetime_design_frequencies_geo(frame, location_frame=location_frame)
    scatter_options = json.loads(scatter_response.json_options)
    geo_options = json.loads(geo_response.json_options)
    assert "Metric" in scatter_response.html
    assert "FA1" in scatter_response.html
    assert "SS1" in scatter_response.html
    assert scatter_options["FA1"]["textStyle"]["fontFamily"] == "monospace"
    assert "Metric" in geo_response.html
    assert "Reference" in geo_response.html
    assert "INFL" in geo_response.html
    assert "ACTU" in geo_response.html
    assert "A01" in geo_response.json_options
    assert geo_options["FA1"]["INFL"]["textStyle"]["fontFamily"] == "monospace"
    assert geo_options["FA1"]["INFL"]["legend"][0]["show"] is False
    assert geo_options["FA1"]["INFL"]["visualMap"]["precision"] == 2
    assert geo_options["FA1"]["INFL"]["geo"]["zoom"] > 0


class TestSanitizeJsonText:
    def test_removes_trailing_commas(self) -> None:
        assert _sanitize_json_text("[1, 2,]") == "[1, 2]"

    def test_removes_trailing_object_comma(self) -> None:
        assert _sanitize_json_text('{"a": 1,}') == '{"a": 1}'

    def test_no_comma_unchanged(self) -> None:
        assert _sanitize_json_text("[1, 2]") == "[1, 2]"


class TestCeitMeasurement:
    def test_timestamp_property(self) -> None:
        meas = CeitMeasurement(
            date="2025-03-12",
            time="12:05:12",
            sensor_identifier="DA8F",
            temperatura=10.0,
            bateria=2.0,
            Tof=[3.0],
            Amplitude=4.0,
            MeasGain=5.0,
        )
        assert meas.timestamp.year == 2025
        assert meas.timestamp.month == 3

    def test_metric_values(self) -> None:
        meas = CeitMeasurement(
            date="2025-03-12",
            time="12:05:12",
            sensor_identifier="DA8F",
            temperatura=10.0,
            bateria=2.0,
            Tof=[3.0],
            Amplitude=4.0,
            MeasGain=5.0,
        )
        values = meas.metric_values()
        assert values["temperature"] == 10.0
        assert values["battery"] == 2.0
        assert values["tof"] == 3.0
        assert values["amplitude"] == 4.0
        assert values["meas_gain"] == 5.0


class TestCeitFrameFromMeasurements:
    def test_produces_long_frame(self) -> None:
        meas = CeitMeasurement(
            date="2025-03-12",
            time="12:05:12",
            sensor_identifier="DA8F",
            temperatura=10.0,
            bateria=2.0,
            Tof=[3.0],
            Amplitude=4.0,
            MeasGain=5.0,
        )
        frame = ceit_frame_from_measurements([meas])
        assert len(frame) == 5
        assert set(frame.columns) == {"sensor_identifier", "timestamp", "metric", "value"}


class TestCeitResultsService:
    def test_analysis_name_for_sensor(self) -> None:
        service = CeitResultsService(model_definition_id=12)
        assert service.analysis_name_for_sensor("DA8F") == f"{CEIT_ANALYSIS_PREFIX}:DA8F"

    def test_build_analysis_definition(self) -> None:
        service = CeitResultsService(model_definition_id=12, location_id=None)
        defn = service.build_analysis_definition("DA8F", source="test.json")
        assert defn.name == f"{CEIT_ANALYSIS_PREFIX}:DA8F"
        assert defn.model_definition_id == 12
        assert defn.location_id is None
        assert defn.source == "test.json"
        assert defn.source_type == "ceit-json"

    def test_build_sensor_results(self) -> None:
        meas = CeitMeasurement(
            date="2025-03-12",
            time="12:05:12",
            sensor_identifier="DA8F",
            temperatura=10.0,
            bateria=2.0,
            Tof=[3.0],
            Amplitude=4.0,
            MeasGain=5.0,
        )
        service = CeitResultsService(model_definition_id=12)
        results = service.build_sensor_results("DA8F", [meas], site_id=1)
        assert len(results) == len(CEIT_METRICS)
        for result in results:
            assert result.site_id == 1

    def test_build_shared_analysis_definition(self) -> None:
        service = CeitResultsService(model_definition_id=12, location_id=88)
        defn = service.build_shared_analysis_definition(source="test.json")
        assert defn.name == "CeitCorrosionMonitoring"
        assert defn.model_definition_id == 12
        assert defn.location_id == 88
        assert defn.source == "test.json"
        assert defn.additional_data["shared_analysis"] is True

    def test_build_sensor_results_with_shared_series_keys_and_signal_linkage(self) -> None:
        meas = CeitMeasurement(
            date="2025-03-12",
            time="12:05:12",
            sensor_identifier="DA8F",
            temperatura=10.0,
            bateria=2.0,
            Tof=[3.0],
            Amplitude=4.0,
            MeasGain=5.0,
        )
        service = CeitResultsService(model_definition_id=12, location_id=88)
        results = service.build_sensor_results(
            "DA8F",
            [meas],
            site_id=77,
            location_id=88,
            analysis_name="CeitCorrosionMonitoring",
            use_stable_series_keys=True,
            signal_id=901,
            signal_history={"id": 501, "legacy_signal_id": "DA8F"},
        )
        assert len(results) == len(CEIT_METRICS)
        assert {result.short_description for result in results} == {
            "DA8F:temperature",
            "DA8F:battery",
            "DA8F:tof",
            "DA8F:amplitude",
            "DA8F:meas_gain",
        }
        for result in results:
            assert result.analysis_name == "CeitCorrosionMonitoring"
            assert result.site_id == 77
            assert result.location_id == 88
            assert result.result_scope == "location"
            assert result.related_object is not None
            assert result.related_object.type == "shm.signal"
            assert result.related_object.id == 901
            assert result.data_additional["signal_id"] == 901

    def test_merge_result_series_appends_new_points(self) -> None:
        from owi.metadatabase.results.models import AnalysisKind, ResultScope, ResultSeries, ResultVector

        existing = ResultSeries(
            analysis_name="CEITSensor:DA8F",
            analysis_kind=AnalysisKind.TIME_SERIES,
            result_scope=ResultScope.SITE,
            short_description="temperature",
            site_id=1,
            vectors=[
                ResultVector(name="timestamp", unit="s", values=[100.0]),
                ResultVector(name="temperature", unit="degC", values=[10.0]),
            ],
        )
        incoming = ResultSeries(
            analysis_name="CEITSensor:DA8F",
            analysis_kind=AnalysisKind.TIME_SERIES,
            result_scope=ResultScope.SITE,
            short_description="temperature",
            site_id=1,
            vectors=[
                ResultVector(name="timestamp", unit="s", values=[100.0, 200.0]),
                ResultVector(name="temperature", unit="degC", values=[10.0, 11.0]),
            ],
        )
        service = CeitResultsService(model_definition_id=12)
        merged, appended = service._merge_result_series(existing, incoming)
        assert appended == 1
        assert len(merged.vectors[0].values) == 2

    def test_merge_result_series_no_new_points(self) -> None:
        from owi.metadatabase.results.models import AnalysisKind, ResultScope, ResultSeries, ResultVector

        existing = ResultSeries(
            analysis_name="CEITSensor:DA8F",
            analysis_kind=AnalysisKind.TIME_SERIES,
            result_scope=ResultScope.SITE,
            short_description="temperature",
            site_id=1,
            vectors=[
                ResultVector(name="timestamp", unit="s", values=[100.0]),
                ResultVector(name="temperature", unit="degC", values=[10.0]),
            ],
        )
        service = CeitResultsService(model_definition_id=12)
        merged, appended = service._merge_result_series(existing, existing)
        assert appended == 0

    def test_upsert_measurements_to_shared_analysis_patches_existing_and_creates_missing(self, tmp_path: Path) -> None:
        payload = tmp_path / "meas.json"
        payload.write_text(
            """
            [
                {
                    "date": "2025-03-12",
                    "time": "12:05:12",
                    "sensor_identifier": "DA8F",
                    "temperatura": 10.0,
                    "bateria": 2.0,
                    "Tof": [3.0],
                    "Amplitude": 4.0,
                    "MeasGain": 5.0
                },
                {
                    "date": "2025-03-12",
                    "time": "12:06:12",
                    "sensor_identifier": "DA8F",
                    "temperatura": 11.0,
                    "bateria": 2.1,
                    "Tof": [3.1],
                    "Amplitude": 4.1,
                    "MeasGain": 5.1
                }
            ]
            """,
            encoding="utf-8",
        )
        api = SharedAnalysisStubCeitApi()
        service = CeitResultsService(api=api, model_definition_id=12, location_id=88)
        result = service.upsert_measurements_to_shared_analysis(
            payload,
            site_id=77,
            location_id=88,
            signal_ids_by_sensor={"DA8F": 901},
            signal_history_by_sensor={"DA8F": {"id": 501, "legacy_signal_id": "DA8F"}},
        )
        assert result["analysis_id"] == 55
        assert result["analysis_name"] == "CeitCorrosionMonitoring"
        assert result["analysis_created"] is False
        summary = result["summary"]
        assert any(row["action"] == "patched" and row["series_key"] == "DA8F:temperature" for row in summary)
        assert any(row["action"] == "created" and row["series_key"] == "DA8F:battery" for row in summary)
        assert api.updated_results
        updated_payload = api.updated_results[0][1]
        assert updated_payload["short_description"] == "DA8F:temperature"
        assert updated_payload["location"] == 88
        assert updated_payload["related_object"] == {"type": "shm.signal", "id": 901}
        assert updated_payload["value_col1"] == [1741781112.0, 1741781172.0]
        assert updated_payload["value_col2"] == [10.0, 11.0]

    def test_upsert_measurements_to_shared_analysis_uses_progress_bar(self, tmp_path: Path) -> None:
        payload = tmp_path / "meas.json"
        payload.write_text(
            """
            [
                {
                    "date": "2025-03-12",
                    "time": "12:05:12",
                    "sensor_identifier": "DA8F",
                    "temperatura": 10.0,
                    "bateria": 2.0,
                    "Tof": [3.0],
                    "Amplitude": 4.0,
                    "MeasGain": 5.0
                }
            ]
            """,
            encoding="utf-8",
        )
        api = SharedAnalysisStubCeitApi()
        service = CeitResultsService(api=api, model_definition_id=12, location_id=88)
        progress = ProgressBarRecorder()

        with patch("owi.metadatabase.results.services.ceit.tqdm", new=progress.factory):
            service.upsert_measurements_to_shared_analysis(
                payload,
                site_id=77,
                location_id=88,
                signal_ids_by_sensor={"DA8F": 901},
            )

        assert len(progress.calls) == 1
        assert progress.calls[0]["kwargs"] == {
            "total": len(CEIT_METRICS),
            "desc": "Uploading shared CEIT result series",
            "unit": "series",
            "disable": False,
        }
        assert progress.calls[0]["updates"] == [1] * len(CEIT_METRICS)

    def test_load_shared_backend_frame_reconstructs_signal_metadata(self) -> None:
        api = SharedAnalysisStubCeitApi()
        service = CeitResultsService(api=api, model_definition_id=12, location_id=88)
        frame = service.load_shared_backend_frame(analysis_id=55)
        assert not frame.empty
        assert set(frame.columns) == {
            "analysis_name",
            "short_description",
            "sensor_identifier",
            "metric",
            "signal_id",
            "timestamp",
            "value",
        }
        assert frame.iloc[0]["analysis_name"] == "CeitCorrosionMonitoring"
        assert frame.iloc[0]["sensor_identifier"] == "DA8F"
        assert frame.iloc[0]["metric"] == "temperature"
        assert frame.iloc[0]["signal_id"] == 901


class TestPlotCeitAnalyses:
    def test_empty_frame_raises(self) -> None:
        with pytest.raises(ValueError, match="No CEIT measurements"):
            plot_ceit_analyses(pd.DataFrame())

    def test_from_measurements_list(self) -> None:
        meas = CeitMeasurement(
            date="2025-03-12",
            time="12:05:12",
            sensor_identifier="DA8F",
            temperatura=10.0,
            bateria=2.0,
            Tof=[3.0],
            Amplitude=4.0,
            MeasGain=5.0,
        )
        response = plot_ceit_analyses([meas])
        assert "DA8F" in response.html
