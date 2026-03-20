"""Tests for validated results models."""

from datetime import datetime, timezone

import pytest

from owi.metadatabase.results import ResultQuery, ResultSeries, ResultVector
from owi.metadatabase.results.models import AnalysisKind, ResultScope


def test_result_series_requires_aligned_vectors() -> None:
    with pytest.raises(ValueError, match="identical lengths"):
        ResultSeries(
            analysis_name="WindSpeedHistogram",
            analysis_kind=AnalysisKind.HISTOGRAM,
            result_scope=ResultScope.SITE,
            short_description="Series",
            site_id=1,
            vectors=[
                ResultVector(name="x", unit="m/s", values=[0.0, 1.0]),
                ResultVector(name="y", unit="count", values=[1.0]),
            ],
        )


def test_result_query_requires_timezone_aware_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResultQuery(timestamp_from=datetime(2024, 1, 1))


def test_result_query_to_backend_filters() -> None:
    query = ResultQuery(
        analysis_name="LifetimeDesignVerification",
        site_id=10,
        timestamp_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    filters = query.to_backend_filters()
    assert filters["analysis__name"] == "LifetimeDesignVerification"
    assert filters["site"] == 10
    assert filters["additional_data__timestamp_from"].startswith("2024-01-01")
