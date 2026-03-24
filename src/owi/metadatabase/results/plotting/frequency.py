"""Additional plotting helpers for lifetime design frequency analyses."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Geo, Scatter
from pyecharts.commons.utils import JsCode
from pyecharts.globals import ChartType

from .response import build_dropdown_plot_response, build_nested_dropdown_plot_response
from .theme import (
    _apply_cartesian_layout,
    _label_opts,
    _legend_opts,
    _title_opts,
    _tooltip_opts,
    _xaxis_opts,
    _yaxis_opts,
)


def _prepare_frequency_frame(data: pd.DataFrame, location_frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach location titles and coordinates to normalized frequency rows."""
    frame = data.copy()
    if location_frame is not None and not location_frame.empty:
        columns = [column for column in ["id", "title", "northing", "easting"] if column in location_frame.columns]
        lookup = location_frame.loc[:, columns].rename(columns={"id": "location_id", "title": "location_title"})
        frame = frame.merge(lookup, how="left", on="location_id")
    if "location_title" not in frame.columns:
        frame["location_title"] = None
    frame["location_title"] = frame["location_title"].fillna(frame.get("turbine", frame["location_id"].astype(str)))
    return frame


def _geo_zoom(frame: pd.DataFrame) -> float:
    """Return a practical zoom factor from the spatial spread of the data."""
    easting_span = float(frame["easting"].max() - frame["easting"].min())
    northing_span = float(frame["northing"].max() - frame["northing"].min())
    span = max(easting_span, northing_span)
    if span <= 0.02:
        return 80
    if span <= 0.05:
        return 50
    if span <= 0.2:
        return 20
    if span <= 1.0:
        return 8
    return 2


def plot_lifetime_design_frequencies_comparison(
    data: pd.DataFrame,
    *,
    location_frame: pd.DataFrame | None = None,
) -> Any:
    """Plot lifetime design frequencies by reference with location-oriented series."""
    frame = _prepare_frequency_frame(data, location_frame=location_frame)
    if frame.empty:
        raise ValueError("No lifetime design frequency data is available to plot.")
    charts: dict[str, Scatter] = {}
    for metric, metric_frame in frame.groupby("metric"):
        chart = Scatter(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = list(dict.fromkeys(metric_frame["reference"].astype(str).tolist()))
        chart.add_xaxis(x_values)
        for location_title, location_frame_group in metric_frame.groupby("location_title"):
            values_by_reference = dict(
                zip(location_frame_group["reference"].astype(str), location_frame_group["y"], strict=False)
            )
            chart.add_yaxis(
                str(location_title),
                cast(Any, [values_by_reference.get(reference) for reference in x_values]),
                symbol_size=12,
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(f"Lifetime Design Frequencies Comparison ({metric})"),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="item"),
            xaxis_opts=_xaxis_opts(name="Reference"),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _apply_cartesian_layout(chart)
        charts[str(metric)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Metric")


def plot_lifetime_design_frequencies_by_location(
    data: pd.DataFrame,
    *,
    location_frame: pd.DataFrame | None = None,
) -> Any:
    """Plot lifetime design frequencies by location with a metric dropdown."""
    frame = _prepare_frequency_frame(data, location_frame=location_frame)
    if frame.empty:
        raise ValueError("No lifetime design frequency data is available to plot.")
    charts: dict[str, Scatter] = {}
    for metric, metric_frame in frame.groupby("metric"):
        chart = Scatter(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = list(dict.fromkeys(metric_frame["location_title"].astype(str).tolist()))
        chart.add_xaxis(x_values)
        for reference, reference_frame in metric_frame.groupby("reference"):
            values_by_location = dict(
                zip(reference_frame["location_title"].astype(str), reference_frame["y"], strict=False)
            )
            chart.add_yaxis(
                str(reference),
                cast(Any, [values_by_location.get(location) for location in x_values]),
                symbol_size=12,
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(f"Lifetime Design Frequencies by Location ({metric})"),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="item"),
            xaxis_opts=_xaxis_opts(name="Location"),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _apply_cartesian_layout(chart)
        charts[str(metric)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Metric")


def plot_lifetime_design_frequencies_geo(
    data: pd.DataFrame,
    *,
    location_frame: pd.DataFrame,
) -> Any:
    """Plot lifetime design frequencies on a geographic scatter map with metric and reference dropdowns."""
    frame = _prepare_frequency_frame(data, location_frame=location_frame)
    required_columns = {"location_title", "northing", "easting"}
    if frame.empty or not required_columns.issubset(frame.columns):
        raise ValueError("Location coordinates are required to build the geographic lifetime design frequency plot.")
    charts: dict[str, dict[str, Geo]] = {}
    coordinate_frame = frame.dropna(subset=["easting", "northing"])
    center = [float(coordinate_frame["easting"].mean()), float(coordinate_frame["northing"].mean())]
    zoom = _geo_zoom(coordinate_frame)
    tooltip_formatter = JsCode(
        "function (params) {"
        "  if (!params || !Array.isArray(params.value) || params.value.length < 3) {"
        "    return params.name;"
        "  }"
        "  return params.name + '<br/>Frequency: ' + Number(params.value[2]).toFixed(2) + ' Hz';"
        "}"
    )
    for metric, metric_frame in frame.groupby("metric"):
        charts[str(metric)] = {}
        coordinate_rows = metric_frame.dropna(subset=["easting", "northing"]).drop_duplicates(subset=["location_title"])
        for reference, reference_frame in metric_frame.groupby("reference"):
            chart = Geo(init_opts=opts.InitOpts(width="100%", height="480px"))
            chart.add_schema(
                maptype="world",
                center=center,
                zoom=zoom,
                is_roam=True,
                itemstyle_opts=opts.ItemStyleOpts(color="#f2efe9", border_color="#8f8a82"),
                emphasis_itemstyle_opts=opts.ItemStyleOpts(color="#ddd7cc"),
            )
            for row in coordinate_rows.to_dict(orient="records"):
                chart.add_coordinate(str(row["location_title"]), float(row["easting"]), float(row["northing"]))
            data_pair = [
                (str(row["location_title"]), float(row["y"]))
                for row in reference_frame.dropna(subset=["easting", "northing"]).to_dict(orient="records")
            ]
            if not data_pair:
                continue
            chart.add(str(reference), data_pair, type_=ChartType.SCATTER, symbol_size=14)
            chart.set_series_opts(label_opts=_label_opts(is_show=False))
            chart.set_global_opts(
                title_opts=_title_opts(f"Lifetime Design Frequencies Map ({metric}, {reference})"),
                legend_opts=opts.LegendOpts(
                    is_show=False,
                    type_="scroll",
                    pos_top="10%",
                    textstyle_opts=opts.TextStyleOpts(font_family="monospace"),
                ),
                tooltip_opts=opts.TooltipOpts(trigger="item", formatter=tooltip_formatter),
                visualmap_opts=opts.VisualMapOpts(
                    min_=float(metric_frame["y"].min()),
                    max_=float(metric_frame["y"].max()),
                    is_calculable=True,
                    pos_top="24%",
                    precision=2,
                ),
            )
            charts[str(metric)][str(reference)] = chart
    return build_nested_dropdown_plot_response(
        charts,
        primary_label="Metric",
        secondary_label="Reference",
        height="480px",
    )
