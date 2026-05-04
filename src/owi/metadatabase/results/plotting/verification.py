"""Plotting helpers for lifetime design verification analyses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Line, Scatter
from pyecharts.commons.utils import JsCode

from .response import build_dropdown_plot_response
from .theme import (
    _apply_cartesian_interactions,
    _apply_cartesian_layout,
    _label_opts,
    _legend_opts,
    _title_opts,
    _tooltip_opts,
    _xaxis_opts,
    _yaxis_opts,
)

_TREND_MARKER_COLOR = "#d62728"
_TREND_MARKER_SIZE = 8
_TREND_MIN_OPACITY = 0.3


def _optional_int(value: Any) -> int | None:
    """Return an integer identifier when the backend scalar is present."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _analysis_source_url(record: Mapping[str, Any]) -> str | None:
    """Return source URL-like text from analysis metadata."""
    for key in ("source_url", "source"):
        value = record.get(key)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        source = str(value)
        if source:
            return source
    return None


def _analysis_sources_by_id(analysis_frame: pd.DataFrame | None) -> tuple[dict[int, str | None], str | None]:
    """Index analysis source metadata by analysis id."""
    if analysis_frame is None or analysis_frame.empty:
        return {}, None

    sources_by_id: dict[int, str | None] = {}
    sources: list[str | None] = []
    for record in analysis_frame.to_dict(orient="records"):
        source = _analysis_source_url(record)
        analysis_id = _optional_int(record.get("id"))
        if analysis_id is None:
            analysis_id = _optional_int(record.get("analysis_id"))
        if analysis_id is not None:
            sources_by_id[analysis_id] = source
        sources.append(source)
    single_source = sources[0] if len(sources) == 1 else None
    return sources_by_id, single_source


def _timestamp(value: Any) -> pd.Timestamp | None:
    """Return a UTC timestamp for tooltip and opacity calculations."""
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return None
    return cast(pd.Timestamp, timestamp)


def _apply_trend_opacity(frame: pd.DataFrame) -> pd.DataFrame:
    """Scale trend marker opacity from oldest to newest timestamp."""
    if frame.empty:
        frame["verification_opacity"] = None
        return frame
    earliest_timestamp = float(frame["timestamp_epoch"].min())
    latest_timestamp = float(frame["timestamp_epoch"].max())
    if latest_timestamp <= earliest_timestamp:
        frame["verification_opacity"] = 1.0
        return frame
    normalized = (frame["timestamp_epoch"] - earliest_timestamp) / (latest_timestamp - earliest_timestamp)
    frame["verification_opacity"] = _TREND_MIN_OPACITY + normalized * (1.0 - _TREND_MIN_OPACITY)
    return frame


def _prepare_water_depth_trend_frame(
    data: pd.DataFrame,
    *,
    location_frame: pd.DataFrame | None,
    analysis_frame: pd.DataFrame | None,
) -> pd.DataFrame:
    """Attach water depth and analysis source metadata to verification rows."""
    if data.empty:
        raise ValueError("No lifetime design verification data is available to plot.")
    frame = data.copy()
    if "location_id" not in frame.columns:
        frame["location_id"] = None
    if location_frame is not None and not location_frame.empty and {"id", "elevation"}.issubset(location_frame.columns):
        lookup = location_frame.loc[:, ["id", "elevation"]].rename(columns={"id": "location_id"})
        frame = frame.merge(lookup, how="left", on="location_id")
    if "elevation" not in frame.columns:
        frame["elevation"] = None

    sources_by_id, single_source = _analysis_sources_by_id(analysis_frame)
    frame["analysis_id"] = frame.get("analysis_id").map(_optional_int) if "analysis_id" in frame.columns else None
    frame["source_url"] = frame["analysis_id"].map(lambda value: sources_by_id.get(value, single_source))
    parsed_timestamps = frame["x"].map(_timestamp)
    frame["timestamp_label"] = parsed_timestamps.map(
        lambda value: None if value is None or pd.isna(value) else value.isoformat()
    )
    frame["timestamp_epoch"] = parsed_timestamps.map(
        lambda value: None if value is None or pd.isna(value) else value.timestamp()
    )
    frame["elevation"] = pd.to_numeric(frame["elevation"], errors="coerce").abs()
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame["metric"] = frame["metric"].astype(str).str.upper()
    frame["turbine"] = frame["turbine"].astype(str)
    frame = frame.dropna(subset=["elevation", "y", "timestamp_epoch"]).copy()
    if frame.empty:
        raise ValueError("No lifetime design verification data with water depth is available to plot.")
    return _apply_trend_opacity(frame)


def _water_depth_trend_tooltip() -> JsCode:
    """Return trend scatter tooltip JS matching verification source-link behavior."""
    return JsCode(
        "function (params) {"
        "  var value = params && params.data ? params.data.value : null;"
        "  if (!Array.isArray(value) || value.length < 4) {"
        "    return params.name;"
        "  }"
        "  function escapeHtml(raw) {"
        "    return String(raw).replace(/[&<>\"]/g, function (match) {"
        "      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;'}[match];"
        "    });"
        "  }"
        "  var source = value.length > 4 ? value[4] : null;"
        "  var sourceLine = '';"
        "  var sourceText = source ? String(source) : '';"
        "  if (sourceText) {"
        "    var escapedSource = escapeHtml(sourceText);"
        "    sourceLine = '<br/>Source: <a href=\"' + escapedSource"
        "      + '\" target=\"_blank\" rel=\"noopener noreferrer\">link</a>';"
        "  }"
        "  return '<strong>' + value[2] + '</strong>'"
        "    + '<br/>Water depth: ' + Number(value[0]).toFixed(2) + ' m'"
        "    + '<br/>Frequency: ' + Number(value[1]).toFixed(4) + ' Hz'"
        "    + '<br/>Timestamp: ' + value[3]"
        "    + sourceLine;"
        "}"
    )


def plot_verification_time_series(data: pd.DataFrame) -> Any:
    """Plot verification metrics over time, one chart per metric with turbine series.

    The returned response contains a dropdown that switches between metrics
    (FA1, SS1, SS2, FA2, …).
    """
    frame = data.copy()
    if frame.empty:
        raise ValueError("No lifetime design verification data is available to plot.")
    charts: dict[str, Line] = {}
    for metric, metric_frame in frame.groupby("metric"):
        chart = Line(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = list(dict.fromkeys(metric_frame["x"].astype(str).tolist()))
        chart.add_xaxis(x_values)
        for turbine, turbine_frame in metric_frame.groupby("turbine"):
            values_by_x = {
                str(x_value): y_value
                for x_value, y_value in turbine_frame[["x", "y"]].itertuples(index=False, name=None)
            }
            chart.add_yaxis(
                str(turbine),
                cast(Any, [values_by_x.get(value) for value in x_values]),
                is_smooth=False,
                is_symbol_show=True,
                symbol_size=6,
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(f"Verification Time-Series ({metric})"),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="axis"),
            xaxis_opts=_xaxis_opts(name="Timestamp", boundary_gap=1 <= len(x_values) <= 3),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _apply_cartesian_layout(chart)
        _apply_cartesian_interactions(chart)
        charts[str(metric)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Metric")


def plot_verification_comparison(data: pd.DataFrame) -> Any:
    """Plot verification metrics per turbine, one chart per turbine with metric series.

    The returned response contains a dropdown that switches between turbines,
    overlaying the different frequency metrics for side-by-side comparison.
    """
    frame = data.copy()
    if frame.empty:
        raise ValueError("No lifetime design verification data is available to plot.")
    charts: dict[str, Line] = {}
    for turbine, turbine_frame in frame.groupby("turbine"):
        chart = Line(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = list(dict.fromkeys(turbine_frame["x"].astype(str).tolist()))
        chart.add_xaxis(x_values)
        for metric, metric_frame in turbine_frame.groupby("metric"):
            values_by_x = {
                str(x_value): y_value
                for x_value, y_value in metric_frame[["x", "y"]].itertuples(index=False, name=None)
            }
            chart.add_yaxis(
                str(metric),
                cast(Any, [values_by_x.get(value) for value in x_values]),
                is_smooth=False,
                is_symbol_show=True,
                symbol_size=6,
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(f"Verification Comparison ({turbine})"),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="axis"),
            xaxis_opts=_xaxis_opts(name="Timestamp", boundary_gap=1 <= len(x_values) <= 3),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _apply_cartesian_layout(chart)
        _apply_cartesian_interactions(chart)
        charts[str(turbine)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Turbine")


def plot_verification_water_depth_trend(
    data: pd.DataFrame,
    *,
    location_frame: pd.DataFrame | None = None,
    analysis_frame: pd.DataFrame | None = None,
) -> Any:
    """Plot verification frequency against water depth, one chart per metric."""
    frame = _prepare_water_depth_trend_frame(
        data,
        location_frame=location_frame,
        analysis_frame=analysis_frame,
    )
    charts: dict[str, Scatter] = {}
    tooltip = _water_depth_trend_tooltip()
    for metric, metric_frame in frame.groupby("metric", sort=True):
        chart = Scatter(init_opts=opts.InitOpts(width="100%", height="420px"))
        chart.add_xaxis([])
        points = [
            {
                "name": str(row["turbine"]),
                "value": [
                    float(row["elevation"]),
                    float(row["y"]),
                    str(row["turbine"]),
                    str(row["timestamp_label"]),
                    row["source_url"],
                ],
                "itemStyle": {
                    "color": _TREND_MARKER_COLOR,
                    "opacity": float(row["verification_opacity"]),
                },
            }
            for row in metric_frame.sort_values(["elevation", "timestamp_epoch"]).to_dict(orient="records")
        ]
        chart.add_yaxis(
            "Verification",
            cast(Any, points),
            symbol="circle",
            symbol_size=_TREND_MARKER_SIZE,
            color=_TREND_MARKER_COLOR,
            label_opts=_label_opts(is_show=False),
            itemstyle_opts=opts.ItemStyleOpts(color=_TREND_MARKER_COLOR),
            tooltip_opts=opts.TooltipOpts(trigger="item", formatter=tooltip, is_enterable=True),
        )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=opts.TitleOpts(is_show=False),
            legend_opts=opts.LegendOpts(is_show=False),
            tooltip_opts=_tooltip_opts(trigger="item"),
            xaxis_opts=opts.AxisOpts(
                type_="value",
                name="Water depth [m]",
                is_scale=True,
                axislabel_opts=_label_opts(),
                name_textstyle_opts=opts.TextStyleOpts(font_family="monospace"),
            ),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _apply_cartesian_layout(chart)
        _apply_cartesian_interactions(chart)
        charts[str(metric)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Metric")
