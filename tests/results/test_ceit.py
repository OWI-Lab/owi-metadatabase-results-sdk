"""Tests for the CEIT corrosion monitoring analysis and plotting."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from owi.metadatabase.results.analyses.ceit import (
    CEIT_METRICS,
    CORROSION_MONITORING_ANALYSIS_NAME,
    CorrosionMonitoring,
    CorrosionMonitoringInput,
    CorrosionMonitoringRow,
    _sanitize_json_text,
    ceit_frame_from_measurements,
    load_ceit_measurements,
)
from owi.metadatabase.results.plotting.ceit import plot_ceit_analyses
from owi.metadatabase.results.plotting.frequency import (
    plot_lifetime_design_frequencies_by_location,
    plot_lifetime_design_frequencies_geo,
)


def _sample_row(*, with_related_object: bool = False) -> CorrosionMonitoringRow:
    payload: dict[str, object] = {
        "date": "2025-03-12",
        "time": "12:05:12",
        "sensor_identifier": "DA8F",
        "temperatura": 10.0,
        "bateria": 2.0,
        "Tof": [3.0],
        "Amplitude": 4.0,
        "MeasGain": 5.0,
        "site_id": 77,
        "location_id": 88,
    }
    if with_related_object:
        payload["related_object"] = {"type": "sensor", "id": 901}
    return CorrosionMonitoringRow.model_validate(payload)


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


def test_plot_ceit_analyses_contains_sensor_dropdown() -> None:
    frame = pd.DataFrame(
        [
            {
                "sensor_identifier": "DA8F",
                "timestamp": "2025-03-12T12:05:12+00:00",
                "metric": "temperature",
                "value": 1.0,
            },
            {
                "sensor_identifier": "DA8F",
                "timestamp": "2025-03-12T12:06:12+00:00",
                "metric": "battery",
                "value": 2.0,
            },
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
    assert scatter_response.frontend_spec is not None
    assert scatter_response.frontend_spec["mode"] == "dropdown"
    assert scatter_response.frontend_spec["controls"][0]["label"] == "Metric"
    assert geo_response.frontend_spec is not None
    assert geo_response.frontend_spec["mode"] == "nested_dropdown"
    assert geo_response.frontend_spec["dependencies"] == ["echarts", "world"]
    assert geo_response.frontend_spec["controls"][0]["label"] == "Metric"
    assert geo_response.frontend_spec["controls"][1]["label"] == "Reference"
    formatter = geo_response.frontend_spec["options_by_primary_key"]["FA1"]["INFL"]["tooltip"]["formatter"]
    assert formatter.startswith("function (params)")


class TestSanitizeJsonText:
    def test_removes_trailing_commas(self) -> None:
        assert _sanitize_json_text("[1, 2,]") == "[1, 2]"

    def test_removes_trailing_object_comma(self) -> None:
        assert _sanitize_json_text('{"a": 1,}') == '{"a": 1}'

    def test_no_comma_unchanged(self) -> None:
        assert _sanitize_json_text("[1, 2]") == "[1, 2]"


class TestCorrosionMonitoringRow:
    def test_timestamp_property(self) -> None:
        row = _sample_row()
        assert row.timestamp.year == 2025
        assert row.timestamp.month == 3

    def test_metric_values(self) -> None:
        values = _sample_row().metric_values()
        assert values["temperature"] == 10.0
        assert values["battery"] == 2.0
        assert values["tof"] == 3.0
        assert values["amplitude"] == 4.0
        assert values["meas_gain"] == 5.0


class TestCorrosionMonitoring:
    def test_validate_inputs_accepts_dict_payload(self) -> None:
        analysis = CorrosionMonitoring()
        validated = analysis.validate_inputs({"rows": [_sample_row().model_dump(by_alias=True)]})
        assert isinstance(validated, CorrosionMonitoringInput)
        assert len(validated.rows) == 1

    def test_compute_produces_long_frame(self) -> None:
        analysis = CorrosionMonitoring()
        frame = analysis.compute({"rows": [_sample_row().model_dump(by_alias=True)]})
        assert len(frame) == len(CEIT_METRICS)
        assert {"analysis_name", "sensor_identifier", "metric", "timestamp", "value"}.issubset(frame.columns)
        assert set(frame["metric"]) == set(CEIT_METRICS)

    def test_to_results_groups_rows_and_keeps_related_object(self) -> None:
        analysis = CorrosionMonitoring()
        results = analysis.to_results({"rows": [_sample_row(with_related_object=True).model_dump(by_alias=True)]})
        assert len(results) == len(CEIT_METRICS)
        assert {result.short_description for result in results} == {
            "DA8F:temperature",
            "DA8F:battery",
            "DA8F:tof",
            "DA8F:amplitude",
            "DA8F:meas_gain",
        }
        for result in results:
            assert result.analysis_name == CORROSION_MONITORING_ANALYSIS_NAME
            assert result.related_object is not None
            assert result.related_object.type == "sensor"
            assert result.related_object.id == 901
            assert result.location_id == 88
            assert result.site_id == 77

    def test_from_results_reconstructs_related_object_columns(self) -> None:
        analysis = CorrosionMonitoring()
        frame = analysis.from_results(
            analysis.to_results({"rows": [_sample_row(with_related_object=True).model_dump(by_alias=True)]})
        )
        assert not frame.empty
        assert frame.iloc[0]["analysis_name"] == CORROSION_MONITORING_ANALYSIS_NAME
        assert frame.iloc[0]["sensor_identifier"] == "DA8F"
        assert frame.iloc[0]["related_object_type"] == "sensor"
        assert frame.iloc[0]["related_object_id"] == 901


class TestPlotCeitAnalyses:
    def test_empty_frame_raises(self) -> None:
        with pytest.raises(ValueError, match="No CEIT measurements"):
            plot_ceit_analyses(pd.DataFrame())

    def test_missing_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required columns"):
            plot_ceit_analyses(pd.DataFrame([{"sensor_identifier": "DA8F"}]))

    def test_processed_frame_renders(self) -> None:
        response = plot_ceit_analyses(ceit_frame_from_measurements([_sample_row()]))
        assert "DA8F" in response.html
