"""Tests for lifetime design verification plotting helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from owi.metadatabase.results.plotting.verification import plot_verification_water_depth_trend


def _sample_verification_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "analysis_id": 19,
                "location_id": 9,
                "x": "2024-01-01T00:00:00+00:00",
                "y": 0.3406,
                "series_name": "WFA01 - FA1",
                "turbine": "WFA01",
                "metric": "FA1",
            },
            {
                "analysis_id": 19,
                "location_id": 10,
                "x": "2024-01-03T00:00:00+00:00",
                "y": 0.3415,
                "series_name": "WFA02 - FA1",
                "turbine": "WFA02",
                "metric": "FA1",
            },
            {
                "analysis_id": 19,
                "location_id": 11,
                "x": "2024-01-02T00:00:00+00:00",
                "y": 0.3421,
                "series_name": "WFA03 - FA1",
                "turbine": "WFA03",
                "metric": "FA1",
            },
            {
                "analysis_id": 19,
                "location_id": 9,
                "x": "2024-01-01T00:00:00+00:00",
                "y": 0.3330,
                "series_name": "WFA01 - SS1",
                "turbine": "WFA01",
                "metric": "SS1",
            },
        ]
    )


def _sample_location_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id": 9, "title": "WFA01", "elevation": -21.5},
            {"id": 10, "title": "WFA02", "elevation": -28.0},
            {"id": 11, "title": "WFA03", "elevation": None},
        ]
    )


def test_water_depth_trend_uses_metric_dropdown_and_numeric_elevation_axis() -> None:
    response = plot_verification_water_depth_trend(
        _sample_verification_frame(),
        location_frame=_sample_location_frame(),
        analysis_frame=pd.DataFrame([{"id": 19, "source_url": "https://example.test/source"}]),
    )

    assert response.frontend_spec is not None
    assert response.frontend_spec["mode"] == "dropdown"
    assert set(response.frontend_spec["options_by_key"]) == {"FA1", "SS1"}

    fa1_chart = response.frontend_spec["options_by_key"]["FA1"]
    verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")

    assert fa1_chart["title"][0]["show"] is False
    assert fa1_chart["legend"][0]["show"] is False
    assert fa1_chart["xAxis"][0]["type"] == "value"
    assert fa1_chart["xAxis"][0]["name"] == "Water depth [m]"
    assert [point["value"][0] for point in verification_series["data"]] == [21.5, 28.0]
    assert [point["value"][1] for point in verification_series["data"]] == [0.3406, 0.3415]
    assert {point["value"][2] for point in verification_series["data"]} == {"WFA01", "WFA02"}


def test_water_depth_trend_matches_verification_marker_style_and_hover_source() -> None:
    response = plot_verification_water_depth_trend(
        _sample_verification_frame(),
        location_frame=_sample_location_frame(),
        analysis_frame=pd.DataFrame([{"id": 19, "source": "https://example.test/notebook"}]),
    )
    assert response.frontend_spec is not None
    fa1_chart = response.frontend_spec["options_by_key"]["FA1"]
    verification_series = next(series for series in fa1_chart["series"] if series["name"] == "Verification")
    opacities = [point["itemStyle"]["opacity"] for point in verification_series["data"]]

    assert verification_series["type"] == "scatter"
    assert verification_series["symbolSize"] == 8
    assert verification_series["itemStyle"]["color"] == "#d62728"
    assert min(opacities) == pytest.approx(0.3)
    assert max(opacities) == pytest.approx(1.0)
    assert {point["value"][4] for point in verification_series["data"]} == {"https://example.test/notebook"}
    assert "Source:" in verification_series["tooltip"]["formatter"]
    assert ">link</a>" in verification_series["tooltip"]["formatter"]
    assert "Water depth:" in verification_series["tooltip"]["formatter"]


def test_water_depth_trend_requires_at_least_one_elevation() -> None:
    with pytest.raises(ValueError, match="water depth"):
        plot_verification_water_depth_trend(
            _sample_verification_frame(),
            location_frame=pd.DataFrame([{"id": 9, "elevation": None}]),
        )
