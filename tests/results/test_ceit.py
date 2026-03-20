"""Tests for CEIT ingestion helpers and custom dropdown plots."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from owi.metadatabase.results import (
    CeitResultsService,
    load_ceit_measurements,
    plot_ceit_analyses,
    plot_lifetime_design_frequencies_by_location,
    plot_lifetime_design_frequencies_geo,
)


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


def test_plot_ceit_analyses_contains_sensor_dropdown() -> None:
    frame = pd.DataFrame(
        [
            {"sensor_identifier": "DA8F", "timestamp": "2025-03-12T12:05:12+00:00", "metric": "temperature", "value": 1.0},
            {"sensor_identifier": "DA8F", "timestamp": "2025-03-12T12:06:12+00:00", "metric": "battery", "value": 2.0},
            {"sensor_identifier": "DA9D", "timestamp": "2025-03-12T12:05:12+00:00", "metric": "temperature", "value": 3.0},
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
    assert geo_options["FA1"]["INFL"]["geo"]["zoom"] == 28