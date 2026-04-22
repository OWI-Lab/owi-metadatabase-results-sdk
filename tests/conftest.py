"""Test fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pytest

from owi.metadatabase.results.models import (
    AnalysisKind,
    ResultScope,
    ResultSeries,
    ResultVector,
)


class StubRepository:
    """Minimal repository stub for service tests."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def list_analyses(self, name: str | None = None, **kwargs: Any) -> pd.DataFrame:
        return pd.DataFrame()

    def list_results(self, query: Any) -> pd.DataFrame:
        return self.frame

    def create_analysis(self, payload: Any) -> Any:
        return payload

    def create_result(self, payload: Any) -> dict[str, Any]:
        return {"item": payload}

    def create_results_bulk(self, payloads: Any) -> dict[str, Any]:
        return {"items": list(payloads)}

    def create_or_update_results_bulk(self, payloads: Any) -> dict[str, Any]:
        return {"items": list(payloads)}

    def update_result(self, result_id: int, payload: Any) -> dict[str, Any]:
        return {"id": result_id, "item": payload}


class StubLocationRepository(StubRepository):
    """Repository stub with location metadata support."""

    def __init__(self, frame: pd.DataFrame, location_frame: pd.DataFrame) -> None:
        super().__init__(frame)
        self.location_frame = location_frame

    def get_location_frame(self, location_ids: list[int]) -> pd.DataFrame:
        result = self.location_frame[self.location_frame["id"].isin(location_ids)].copy()
        return pd.DataFrame(result)


@pytest.fixture()
def sample_histogram_results() -> list[ResultSeries]:
    """Pre-built histogram result series for testing."""
    from owi.metadatabase.results import WindSpeedHistogram

    return WindSpeedHistogram().to_results(
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


@pytest.fixture()
def sample_frequency_results() -> list[ResultSeries]:
    """Pre-built frequency comparison result series for testing."""
    from owi.metadatabase.results import LifetimeDesignFrequencies

    return LifetimeDesignFrequencies().to_results(
        {
            "rows": [
                {"turbine": "WFA03", "reference": "INFL", "FA1": 0.3406, "SS1": 0.3407, "location_id": 9},
                {"turbine": "WFA03", "reference": "ACTU", "FA1": 0.3330, "SS1": 0.3332, "location_id": 9},
            ]
        }
    )


@pytest.fixture()
def sample_verification_results() -> list[ResultSeries]:
    """Pre-built verification result series for testing."""
    from owi.metadatabase.results.analyses.lifetime_design_verification import LifetimeDesignVerification

    return LifetimeDesignVerification().to_results(
        {
            "rows": [
                {
                    "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    "turbine": "WFA03",
                    "FA1": 0.356,
                    "SS1": 0.357,
                    "location_id": 5,
                },
                {
                    "timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
                    "turbine": "WFA03",
                    "FA1": 0.355,
                    "SS1": 0.356,
                    "location_id": 5,
                },
            ]
        }
    )


@pytest.fixture()
def sample_result_series() -> ResultSeries:
    """Return a single valid ResultSeries for generic testing."""
    return ResultSeries(
        analysis_name="TestAnalysis",
        analysis_kind=AnalysisKind.HISTOGRAM,
        result_scope=ResultScope.SITE,
        short_description="test-series",
        site_id=1,
        vectors=[
            ResultVector(name="x", unit="m/s", values=[0.0, 1.0, 2.0]),
            ResultVector(name="y", unit="count", values=[10.0, 20.0, 30.0]),
        ],
    )


@pytest.fixture()
def sample_location_frame() -> pd.DataFrame:
    """Location metadata fixture for geo-plot tests."""
    return pd.DataFrame(
        [
            {"id": 9, "title": "WFA03", "northing": 51.5, "easting": 2.8},
            {"id": 10, "title": "WFB07", "northing": 51.6, "easting": 2.9},
        ]
    )
