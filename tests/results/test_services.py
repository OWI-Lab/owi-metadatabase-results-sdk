"""Tests for high-level services and analyses."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from owi.metadatabase.results import LifetimeDesignFrequencies, ResultsService, WindSpeedHistogram
from owi.metadatabase.results.analyses.lifetime_design_verification import LifetimeDesignVerification


class StubRepository:
    """Small repository stub for service tests."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def list_results(self, query):
        return self.frame

    def create_analysis(self, payload):
        return payload

    def create_results_bulk(self, payloads):
        return {"items": list(payloads)}


def test_wind_speed_histogram_to_results_and_plot() -> None:
    analysis = WindSpeedHistogram()
    results = analysis.to_results(
        {
            "series": [
                {
                    "title": "Design",
                    "scope_label": "Site",
                    "site_id": 1,
                    "bins": [(0.0, 1.0), (1.0, 2.0)],
                    "values": [1.0, 2.0],
                }
            ]
        }
    )
    response = analysis.plot(results)
    assert len(results) == 1
    assert "Design" in response.html
    assert response.notebook is not None
    assert "series" in response.json_options


def test_lifetime_design_verification_to_results() -> None:
    analysis = LifetimeDesignVerification()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "timestamp": datetime(2024, 1, 1, tzinfo=UTC),
                    "turbine": "BBA01",
                    "FA1": 0.356,
                    "SS1": 0.357,
                    "location_id": 5,
                },
                {
                    "timestamp": datetime(2024, 1, 2, tzinfo=UTC),
                    "turbine": "BBA01",
                    "FA1": 0.355,
                    "SS1": 0.356,
                    "location_id": 5,
                },
            ]
        }
    )
    assert len(results) == 2
    assert results[0].location_id == 5


def test_results_service_get_results() -> None:
    analysis = WindSpeedHistogram()
    series = analysis.to_results(
        {
            "series": [
                {
                    "title": "Design",
                    "scope_label": "Site",
                    "site_id": 1,
                    "bins": [(0.0, 1.0), (1.0, 2.0)],
                    "values": [1.0, 2.0],
                }
            ]
        }
    )[0]
    payload = series.to_record_payload(analysis_id=11)
    frame = pd.DataFrame([payload])
    service = ResultsService(repository=StubRepository(frame))
    result = service.get_results("WindSpeedHistogram")
    assert list(result.columns) == ["series_name", "scope", "bin_left", "bin_right", "value"]
    assert len(result) == 2


def test_lifetime_design_frequencies_to_results() -> None:
    analysis = LifetimeDesignFrequencies()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "turbine": "BBA01",
                    "reference": "INFL",
                    "FA1": 0.3406,
                    "SS1": 0.3407,
                    "location_id": 9,
                },
                {
                    "turbine": "BBA01",
                    "reference": "ACTU",
                    "FA1": 0.3330,
                    "SS1": 0.3332,
                    "location_id": 9,
                },
            ]
        }
    )
    assert len(results) == 2
    reconstructed = analysis.from_results(results)
    assert set(reconstructed["reference"]) == {"INFL", "ACTU"}
