"""Tests for wind speed histogram analysis."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from owi.metadatabase.results import WindSpeedHistogram
from owi.metadatabase.results.analyses.wind_speed_histogram import (
    HistogramSeriesInput,
    WindSpeedHistogramInput,
)
from owi.metadatabase.results.models import AnalysisKind, ResultScope


class TestHistogramSeriesInput:
    def test_mismatched_bins_and_values_rejected(self) -> None:
        with pytest.raises(ValidationError, match="same length"):
            HistogramSeriesInput(
                title="Test",
                scope_label="Site",
                bins=[(0.0, 1.0), (1.0, 2.0)],
                values=[1.0],
            )

    def test_valid_construction(self) -> None:
        series = HistogramSeriesInput(
            title="Design",
            scope_label="Site",
            bins=[(0.0, 1.0)],
            values=[5.0],
        )
        assert series.title == "Design"


class TestWindSpeedHistogramInput:
    def test_requires_at_least_one_series(self) -> None:
        with pytest.raises(ValidationError):
            WindSpeedHistogramInput(series=[])

    def test_default_units(self) -> None:
        inp = WindSpeedHistogramInput(
            series=[
                HistogramSeriesInput(
                    title="T",
                    scope_label="S",
                    bins=[(0.0, 1.0)],
                    values=[1.0],
                )
            ]
        )
        assert inp.bin_unit == "m/s"
        assert inp.value_unit == "count"


class TestWindSpeedHistogram:
    def test_class_attributes(self) -> None:
        analysis = WindSpeedHistogram()
        assert analysis.analysis_name == "WindSpeedHistogram"
        assert analysis.analysis_kind == AnalysisKind.HISTOGRAM.value
        assert analysis.default_plot_type == "histogram"

    def test_validate_inputs_dict(self) -> None:
        analysis = WindSpeedHistogram()
        result = analysis.validate_inputs(
            {"series": [{"title": "T", "scope_label": "S", "bins": [(0.0, 1.0)], "values": [1.0]}]}
        )
        assert isinstance(result, WindSpeedHistogramInput)

    def test_validate_inputs_passthrough(self) -> None:
        analysis = WindSpeedHistogram()
        inp = WindSpeedHistogramInput(
            series=[
                HistogramSeriesInput(
                    title="T",
                    scope_label="S",
                    bins=[(0.0, 1.0)],
                    values=[1.0],
                )
            ]
        )
        assert analysis.validate_inputs(inp) is inp

    def test_compute_produces_flat_table(self) -> None:
        analysis = WindSpeedHistogram()
        df = analysis.compute(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "bins": [(0.0, 1.0), (1.0, 2.0)],
                        "values": [5.0, 10.0],
                    }
                ]
            }
        )
        assert list(df.columns) == ["series_name", "scope", "bin_left", "bin_right", "value"]
        assert len(df) == 2

    def test_to_results_three_vectors(self) -> None:
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0), (1.0, 2.0)],
                        "values": [5.0, 10.0],
                    }
                ]
            }
        )
        assert len(results) == 1
        assert len(results[0].vectors) == 3
        assert results[0].vectors[0].name == "bin_left"
        assert results[0].vectors[1].name == "value"
        assert results[0].vectors[2].name == "bin_right"

    def test_to_results_site_scope(self) -> None:
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0)],
                        "values": [5.0],
                    }
                ]
            }
        )
        assert results[0].result_scope == ResultScope.SITE

    def test_to_results_location_scope(self) -> None:
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Loc",
                        "scope_label": "Location",
                        "location_id": 7,
                        "bins": [(0.0, 1.0)],
                        "values": [5.0],
                    }
                ]
            }
        )
        assert results[0].result_scope == ResultScope.LOCATION
        assert results[0].location_id == 7

    def test_from_results_roundtrip(self) -> None:
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0), (1.0, 2.0)],
                        "values": [5.0, 10.0],
                    }
                ]
            }
        )
        df = analysis.from_results(results)
        assert list(df.columns) == ["series_name", "scope", "bin_left", "bin_right", "value"]
        assert len(df) == 2
        assert df["bin_left"].tolist() == [0.0, 1.0]
        assert df["value"].tolist() == [5.0, 10.0]

    def test_from_results_two_vector_fallback(self) -> None:
        """from_results handles 2-vector results gracefully (no bin_right)."""
        from owi.metadatabase.results.models import AnalysisKind, ResultScope, ResultSeries, ResultVector

        series = ResultSeries(
            analysis_name="WindSpeedHistogram",
            analysis_kind=AnalysisKind.HISTOGRAM,
            result_scope=ResultScope.SITE,
            short_description="Test",
            site_id=1,
            data_additional={"scope_label": "Site"},
            vectors=[
                ResultVector(name="bin_left", unit="m/s", values=[0.0, 1.0]),
                ResultVector(name="value", unit="count", values=[5.0, 10.0]),
            ],
        )
        analysis = WindSpeedHistogram()
        df = analysis.from_results([series])
        assert df["bin_right"].tolist() == [None, None]

    def test_to_results_stores_metadata(self) -> None:
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0)],
                        "values": [5.0],
                        "metadata": {"source": "test"},
                    }
                ]
            }
        )
        assert results[0].data_additional["scope_label"] == "Site"
        assert results[0].data_additional["source"] == "test"
        assert results[0].data_additional["series_key"] == "Design"

    def test_plot_returns_valid_response(self) -> None:
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0), (1.0, 2.0)],
                        "values": [5.0, 10.0],
                    }
                ]
            }
        )
        response = analysis.plot(results)
        assert response.html
        assert response.json_options
        options = json.loads(response.json_options)
        assert "series" in options

    def test_multiple_series(self) -> None:
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0)],
                        "values": [5.0],
                    },
                    {
                        "title": "Measured",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0)],
                        "values": [3.0],
                    },
                ]
            }
        )
        assert len(results) == 2
        df = analysis.from_results(results)
        assert set(df["series_name"]) == {"Design", "Measured"}
