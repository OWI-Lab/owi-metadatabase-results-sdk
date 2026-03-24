"""Tests for plotting strategies and chart builders."""

from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
import pytest
from pyecharts.charts import Bar, Geo
from pyecharts.globals import ChartType

from owi.metadatabase.results.models import PlotRequest, PlotResponse
from owi.metadatabase.results.plotting import (
    HistogramPlotStrategy,
    TimeSeriesPlotStrategy,
    _apply_cartesian_layout,
    _apply_monospace_theme,
    _selected_option_suffix,
    build_dropdown_plot_response,
    build_nested_dropdown_plot_response,
    get_plot_strategy,
)


class TestThemeHelpers:
    def test_apply_monospace_theme_sets_font(self) -> None:
        chart = Bar()
        _apply_monospace_theme(chart)
        assert chart.options["textStyle"]["fontFamily"] == "monospace"

    def test_apply_monospace_theme_preserves_existing(self) -> None:
        chart = Bar()
        chart.options["textStyle"] = {"fontSize": 14}
        _apply_monospace_theme(chart)
        assert chart.options["textStyle"]["fontFamily"] == "monospace"
        assert chart.options["textStyle"]["fontSize"] == 14

    def test_apply_cartesian_layout_dict(self) -> None:
        chart = Bar()
        chart.options["grid"] = {"top": "0%"}
        _apply_cartesian_layout(chart)
        assert chart.options["grid"]["top"] == "30%"

    def test_apply_cartesian_layout_list(self) -> None:
        chart = Bar()
        chart.options["grid"] = [{"top": "0%"}]
        _apply_cartesian_layout(chart)
        assert chart.options["grid"][0]["top"] == "30%"

    def test_apply_cartesian_layout_empty_list(self) -> None:
        chart = Bar()
        chart.options["grid"] = []
        _apply_cartesian_layout(chart)
        assert isinstance(chart.options["grid"], list)

    def test_apply_cartesian_layout_missing(self) -> None:
        chart = Bar()
        if "grid" in chart.options:
            del chart.options["grid"]
        _apply_cartesian_layout(chart)
        assert "top" in chart.options["grid"]

    def test_selected_option_suffix_match(self) -> None:
        assert _selected_option_suffix("FA1", "FA1") == ' selected="selected"'

    def test_selected_option_suffix_no_match(self) -> None:
        assert _selected_option_suffix("FA1", "SS1") == ""


class TestHistogramPlotStrategy:
    def test_render_returns_plot_response(self) -> None:
        strategy = HistogramPlotStrategy()
        data = pd.DataFrame(
            [
                {"series_name": "Design", "scope": "Site", "bin_left": 0.0, "bin_right": 1.0, "value": 5.0},
                {"series_name": "Design", "scope": "Site", "bin_left": 1.0, "bin_right": 2.0, "value": 10.0},
            ]
        )
        request = PlotRequest(analysis_name="WindSpeedHistogram")
        response = strategy.render(data, request)
        assert isinstance(response, PlotResponse)
        assert response.html
        options = json.loads(response.json_options)
        assert "series" in options

    def test_render_nan_bin_right(self) -> None:
        strategy = HistogramPlotStrategy()
        data = pd.DataFrame(
            [
                {"series_name": "Design", "scope": "Site", "bin_left": 0.0, "bin_right": None, "value": 5.0},
            ]
        )
        request = PlotRequest(analysis_name="Test")
        response = strategy.render(data, request)
        assert response.html


class TestTimeSeriesPlotStrategy:
    def test_render_returns_plot_response(self) -> None:
        strategy = TimeSeriesPlotStrategy()
        data = pd.DataFrame(
            [
                {"series_name": "A01 - FA1", "x": "2024-01-01T00:00:00+00:00", "y": 0.356},
                {"series_name": "A01 - FA1", "x": "2024-01-02T00:00:00+00:00", "y": 0.355},
            ]
        )
        request = PlotRequest(analysis_name="Verification", title="Custom Title")
        response = strategy.render(data, request)
        assert isinstance(response, PlotResponse)
        options = json.loads(response.json_options)
        assert options["title"][0]["text"] == "Custom Title"

    def test_render_uses_analysis_name_as_title(self) -> None:
        strategy = TimeSeriesPlotStrategy()
        data = pd.DataFrame([{"series_name": "S1", "x": "2024-01-01", "y": 1.0}])
        request = PlotRequest(analysis_name="MyAnalysis")
        response = strategy.render(data, request)
        options = json.loads(response.json_options)
        assert options["title"][0]["text"] == "MyAnalysis"


class TestGetPlotStrategy:
    def test_known_types(self) -> None:
        assert isinstance(get_plot_strategy("histogram"), HistogramPlotStrategy)
        assert isinstance(get_plot_strategy("time_series"), TimeSeriesPlotStrategy)
        assert isinstance(get_plot_strategy("comparison"), TimeSeriesPlotStrategy)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(KeyError):
            get_plot_strategy("nonexistent")


class TestBuildDropdownPlotResponse:
    def test_empty_charts_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one chart"):
            build_dropdown_plot_response({}, dropdown_label="Test")

    def test_single_chart(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a", "b"])
        chart.add_yaxis("S1", [1, 2])
        response = build_dropdown_plot_response({"key1": chart}, dropdown_label="Metric")
        assert "Metric" in response.html
        assert "key1" in response.html
        assert "owi-results-dropdown-item" in response.html
        assert "<select" not in response.html
        assert "Theme" not in response.html
        assert isinstance(response, PlotResponse)

    def test_multiple_charts(self) -> None:
        chart1 = Bar()
        chart1.add_xaxis(["a"])
        chart1.add_yaxis("S1", [1])
        chart2 = Bar()
        chart2.add_xaxis(["b"])
        chart2.add_yaxis("S2", [2])
        response = build_dropdown_plot_response(
            {"FA1": chart1, "SS1": chart2}, dropdown_label="Metric", default_key="SS1"
        )
        assert "FA1" in response.html
        assert "SS1" in response.html

    def test_does_not_include_theme_selector(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        response = build_dropdown_plot_response({"FA1": chart}, dropdown_label="Metric")
        assert "Theme" not in response.html
        assert 'data-value="light"' not in response.html
        assert 'data-value="dark"' not in response.html

    def test_iframe_notebook_html_resizes_embedded_output(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        response = build_dropdown_plot_response({"FA1": chart}, dropdown_label="Metric")
        assert response.notebook is not None
        assert "ResizeObserver" in response.notebook.data
        assert "window.frameElement.style.height" in response.notebook.data

    def test_prefers_html_notebook_renderer_when_available(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        widget_sentinel = object()
        with (
            patch(
                "owi.metadatabase.results.plotting.response.HTML",
                return_value=widget_sentinel,
            ) as html_builder,
            patch(
                "owi.metadatabase.results.plotting.response._build_widget_dropdown",
                return_value=object(),
            ) as widget_builder,
        ):
            response = build_dropdown_plot_response({"key1": chart}, dropdown_label="Metric")
        html_builder.assert_called_once()
        widget_builder.assert_not_called()
        assert response.notebook is widget_sentinel

    def test_falls_back_to_widget_notebook_renderer_without_html(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        widget_sentinel = object()
        with (
            patch("owi.metadatabase.results.plotting.response.HTML", None),
            patch(
                "owi.metadatabase.results.plotting.response._build_widget_dropdown",
                return_value=widget_sentinel,
            ) as widget_builder,
        ):
            response = build_dropdown_plot_response({"key1": chart}, dropdown_label="Metric")
        widget_builder.assert_called_once()
        assert response.notebook is widget_sentinel


class TestBuildNestedDropdownPlotResponse:
    def test_empty_charts_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one chart"):
            build_nested_dropdown_plot_response(
                {},
                primary_label="Metric",
                secondary_label="Reference",
            )

    def test_empty_secondary_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one chart"):
            build_nested_dropdown_plot_response(
                {"FA1": {}},
                primary_label="Metric",
                secondary_label="Reference",
            )

    def test_valid_nested(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        response = build_nested_dropdown_plot_response(
            {"FA1": {"INFL": chart}},
            primary_label="Metric",
            secondary_label="Reference",
        )
        assert "Metric" in response.html
        assert "Reference" in response.html
        assert "FA1" in response.html
        assert "INFL" in response.html
        assert "owi-results-dropdown-item" in response.html
        assert "<select" not in response.html
        assert "Theme" not in response.html

    def test_includes_geo_map_dependency(self) -> None:
        chart = Geo()
        chart.add_schema(maptype="world")
        chart.add_coordinate("A", 2.8, 51.5)
        chart.add("INFL", [("A", 0.34)], type_=ChartType.SCATTER)
        response = build_nested_dropdown_plot_response(
            {"FA1": {"INFL": chart}},
            primary_label="Metric",
            secondary_label="Reference",
        )
        assert "maps/world.js" in response.html

    def test_nested_does_not_include_theme_selector(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        response = build_nested_dropdown_plot_response(
            {"FA1": {"INFL": chart}},
            primary_label="Metric",
            secondary_label="Reference",
        )
        assert "Theme" not in response.html
        assert 'data-value="light"' not in response.html
        assert 'data-value="dark"' not in response.html

    def test_nested_renderer_resets_chart_before_rerender(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        response = build_nested_dropdown_plot_response(
            {"FA1": {"INFL": chart}, "SS1": {"INFL": chart}},
            primary_label="Metric",
            secondary_label="Reference",
        )
        assert "function resetChart()" in response.html
        assert "resetChart();" in response.html

    def test_prefers_nested_html_notebook_renderer_when_available(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        widget_sentinel = object()
        with (
            patch(
                "owi.metadatabase.results.plotting.response.HTML",
                return_value=widget_sentinel,
            ) as html_builder,
            patch(
                "owi.metadatabase.results.plotting.response._build_nested_widget_dropdown",
                return_value=object(),
            ) as widget_builder,
        ):
            response = build_nested_dropdown_plot_response(
                {"FA1": {"INFL": chart}},
                primary_label="Metric",
                secondary_label="Reference",
            )
        html_builder.assert_called_once()
        widget_builder.assert_not_called()
        assert response.notebook is widget_sentinel

    def test_falls_back_to_nested_widget_notebook_renderer_without_html(self) -> None:
        chart = Bar()
        chart.add_xaxis(["a"])
        chart.add_yaxis("S1", [1])
        widget_sentinel = object()
        with (
            patch("owi.metadatabase.results.plotting.response.HTML", None),
            patch(
                "owi.metadatabase.results.plotting.response._build_nested_widget_dropdown",
                return_value=widget_sentinel,
            ) as widget_builder,
        ):
            response = build_nested_dropdown_plot_response(
                {"FA1": {"INFL": chart}},
                primary_label="Metric",
                secondary_label="Reference",
            )
        widget_builder.assert_called_once()
        assert response.notebook is widget_sentinel
