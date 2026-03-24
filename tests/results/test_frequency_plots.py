"""Tests for frequency-specific plotting helpers."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from owi.metadatabase.results.plotting.frequency import (
    _prepare_frequency_frame,
    plot_lifetime_design_frequencies_by_location,
    plot_lifetime_design_frequencies_comparison,
    plot_lifetime_design_frequencies_geo,
)


def _sample_frequency_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"location_id": 1, "turbine": "A01", "metric": "FA1", "reference": "INFL", "y": 0.34},
            {"location_id": 1, "turbine": "A01", "metric": "FA1", "reference": "ACTU", "y": 0.33},
            {"location_id": 2, "turbine": "A02", "metric": "FA1", "reference": "INFL", "y": 0.32},
            {"location_id": 2, "turbine": "A02", "metric": "FA1", "reference": "ACTU", "y": 0.31},
        ]
    )


def _sample_location_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id": 1, "title": "A01", "northing": 51.5, "easting": 2.8},
            {"id": 2, "title": "A02", "northing": 51.6, "easting": 2.9},
        ]
    )


class TestPrepareFrequencyFrame:
    def test_merges_location_titles(self) -> None:
        frame = _prepare_frequency_frame(_sample_frequency_data(), _sample_location_frame())
        assert "location_title" in frame.columns
        assert set(frame["location_title"]) == {"A01", "A02"}

    def test_without_location_frame(self) -> None:
        frame = _prepare_frequency_frame(_sample_frequency_data())
        assert "location_title" in frame.columns

    def test_with_empty_location_frame(self) -> None:
        frame = _prepare_frequency_frame(_sample_frequency_data(), pd.DataFrame())
        assert "location_title" in frame.columns


class TestComparisonPlot:
    def test_empty_data_raises(self) -> None:
        empty = pd.DataFrame(columns=["metric", "reference", "y", "location_id", "turbine"])
        with pytest.raises(ValueError, match="No lifetime design frequency"):
            plot_lifetime_design_frequencies_comparison(empty)

    def test_returns_dropdown_response(self) -> None:
        response = plot_lifetime_design_frequencies_comparison(
            _sample_frequency_data(), location_frame=_sample_location_frame()
        )
        assert "Metric" in response.html
        options = json.loads(response.json_options)
        assert "FA1" in options


class TestByLocationPlot:
    def test_empty_data_raises(self) -> None:
        empty = pd.DataFrame(columns=["metric", "reference", "y", "location_id", "turbine"])
        with pytest.raises(ValueError, match="No lifetime design frequency"):
            plot_lifetime_design_frequencies_by_location(empty)

    def test_returns_dropdown_response(self) -> None:
        response = plot_lifetime_design_frequencies_by_location(
            _sample_frequency_data(), location_frame=_sample_location_frame()
        )
        assert "Metric" in response.html


class TestGeoPlot:
    def test_empty_data_raises(self) -> None:
        empty = pd.DataFrame(columns=["metric", "reference", "y", "location_id", "turbine"])
        with pytest.raises(ValueError, match="Location coordinates"):
            plot_lifetime_design_frequencies_geo(empty, location_frame=pd.DataFrame())

    def test_missing_coordinate_columns_raises(self) -> None:
        data = _sample_frequency_data()
        with pytest.raises(ValueError, match="Location coordinates"):
            plot_lifetime_design_frequencies_geo(data, location_frame=pd.DataFrame(columns=["id", "title"]))

    def test_returns_nested_dropdown_response(self) -> None:
        response = plot_lifetime_design_frequencies_geo(
            _sample_frequency_data(), location_frame=_sample_location_frame()
        )
        assert "Metric" in response.html
        assert "Reference" in response.html
        options = json.loads(response.json_options)
        assert "FA1" in options
        assert "INFL" in options["FA1"]
