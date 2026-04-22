"""Plotting helpers for combined frequency and verification comparisons."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Line, Scatter
from pyecharts.commons.utils import JsCode

from ..models import ResultQuery
from .definitions import PlotDefinition, PlotSourceData, PlotSourceSpec
from .response import build_dropdown_plot_response
from .theme import (
    _apply_cartesian_layout,
    _label_opts,
    _legend_opts,
    _tooltip_opts,
    _xaxis_opts,
    _yaxis_opts,
)

LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME = "LifetimeDesignFrequencies"
LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME = "LifetimeDesignVerification"
_FREQUENCY_SOURCE_KEY = "frequency"
_VERIFICATION_SOURCE_KEY = "verification"
_REFERENCE_LINE_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#8c564b", "#17becf")
_VERIFICATION_COLOR = "#d62728"
_VERIFICATION_MIN_OPACITY = 0.3
_REFERENCE_SYMBOL_SIZE = 5
_VERIFICATION_SYMBOL_SIZE = 8
_REQUIRED_COLUMNS = {"asset", "metric", "y"}
_NORMALIZED_COLUMNS = [
    "asset",
    "metric",
    "y",
    "timestamp_label",
    "timestamp_epoch",
    "hover_name",
    "reference_label",
    "reference_order",
]
_COMBINED_FREQUENCY_VERIFICATION_COLUMNS = list(_NORMALIZED_COLUMNS)


def _require_columns(frame: pd.DataFrame, required_columns: set[str], *, frame_name: str) -> None:
    """Require the given normalized frame columns when the frame is non-empty."""
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"{frame_name} is missing required columns: {missing}.")


def _build_plot_source_query(
    query: ResultQuery,
    analysis_name: str,
    *,
    owner_analysis_name: str,
) -> ResultQuery:
    """Clone the base query for one source analysis."""
    backend_filters = {
        key: value
        for key, value in query.backend_filters.items()
        if key not in {"analysis__id", "analysis__name"}
    }
    return query.model_copy(
        update={
            "analysis_name": analysis_name,
            "analysis_id": query.analysis_id if analysis_name == owner_analysis_name else None,
            "backend_filters": backend_filters,
        }
    )


def _build_frequency_verification_sources(
    query: ResultQuery,
    owner_analysis_name: str,
) -> tuple[PlotSourceSpec, ...]:
    """Return the named sources required by the assembled frequency/verification plot."""
    del query
    return (
        PlotSourceSpec(
            key=_FREQUENCY_SOURCE_KEY,
            analysis_name=LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME,
            build_query=lambda source_query, source_owner, analysis_name=LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME: (
                _build_plot_source_query(source_query, analysis_name, owner_analysis_name=source_owner)
            ),
        ),
        PlotSourceSpec(
            key=_VERIFICATION_SOURCE_KEY,
            analysis_name=LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME,
            build_query=lambda source_query, source_owner, analysis_name=LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME: (
                _build_plot_source_query(source_query, analysis_name, owner_analysis_name=source_owner)
            ),
        ),
    )


def assemble_frequency_verification_comparison_frame(sources_by_key: Mapping[str, PlotSourceData]) -> pd.DataFrame:
    """Merge normalized frequency and verification frames for the combined plot."""
    rows: list[dict[str, Any]] = []
    frequency_source = sources_by_key.get(_FREQUENCY_SOURCE_KEY)
    verification_source = sources_by_key.get(_VERIFICATION_SOURCE_KEY)
    frequency_frame = pd.DataFrame() if frequency_source is None else frequency_source.frame
    verification_frame = pd.DataFrame() if verification_source is None else verification_source.frame

    if not frequency_frame.empty:
        _require_columns(
            frequency_frame,
            {"turbine", "metric", "reference", "y"},
            frame_name="Frequency frame",
        )
        frequency_reference_order: dict[tuple[str, str], int] = {}
        for metric, metric_frame in frequency_frame.groupby("metric", sort=False):
            ordered_references = dict.fromkeys(metric_frame["reference"].astype(str).tolist())
            for index, reference_label in enumerate(ordered_references, start=1):
                frequency_reference_order[(str(metric).upper(), str(reference_label))] = index

        for record in frequency_frame.to_dict(orient="records"):
            metric = str(record["metric"]).upper()
            reference_label = str(record["reference"])
            rows.append(
                {
                    "asset": str(record["turbine"]),
                    "metric": metric,
                    "y": float(record["y"]),
                    "timestamp_label": None,
                    "timestamp_epoch": None,
                    "hover_name": str(record["turbine"]),
                    "reference_label": reference_label,
                    "reference_order": frequency_reference_order[(metric, reference_label)],
                }
            )

    if not verification_frame.empty:
        _require_columns(
            verification_frame,
            {"turbine", "metric", "x", "y"},
            frame_name="Verification frame",
        )
        for record in verification_frame.to_dict(orient="records"):
            timestamp = pd.to_datetime(record["x"], utc=True, errors="coerce")
            rows.append(
                {
                    "asset": str(record["turbine"]),
                    "metric": str(record["metric"]).upper(),
                    "y": float(record["y"]),
                    "timestamp_label": None if pd.isna(timestamp) else timestamp.isoformat(),
                    "timestamp_epoch": None if pd.isna(timestamp) else timestamp.timestamp(),
                    "hover_name": str(record["turbine"]),
                    "reference_label": None,
                    "reference_order": None,
                }
            )

    return pd.DataFrame(rows, columns=_COMBINED_FREQUENCY_VERIFICATION_COLUMNS)


def _render_frequency_verification_plot(
    sources_by_key: Mapping[str, PlotSourceData],
    request: Any,
) -> Any:
    """Render the assembled frequency/verification comparison plot."""
    del request
    return plot_frequency_verification_comparison(assemble_frequency_verification_comparison_frame(sources_by_key))


def build_frequency_verification_plot_definition() -> PlotDefinition:
    """Return the registered assembled frequency/verification plot definition."""
    return PlotDefinition(
        owner_analysis_names=(
            LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME,
            LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME,
        ),
        plot_type="assembled",
        build_sources=_build_frequency_verification_sources,
        render=_render_frequency_verification_plot,
    )


def _coerce_timestamp(value: Any) -> pd.Timestamp | None:
    """Return a UTC timestamp when the raw value is parseable."""
    if value is None or pd.isna(value):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    else:
        timestamp = pd.to_datetime(numeric_value, unit="s", utc=True, errors="coerce")
    if pd.isna(timestamp):
        return None
    return cast(pd.Timestamp, timestamp)


def _normalize_frequency_verification_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize the combined comparison frame expected by the plotter.

    Expected input is the assembled, long-form plotting frame produced by the
    custom plotting layer, not raw backend result rows.
    """
    if data.empty:
        return pd.DataFrame(columns=_NORMALIZED_COLUMNS)
    missing_columns = _REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Frequency verification plot data is missing required columns: {missing}.")
    frame = data.copy()
    for column in _NORMALIZED_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    parsed_from_epoch = frame["timestamp_epoch"].map(_coerce_timestamp)
    parsed_from_label = frame["timestamp_label"].map(_coerce_timestamp)
    parsed_timestamps = parsed_from_epoch.where(parsed_from_epoch.notna(), parsed_from_label)
    frame["timestamp_epoch"] = parsed_timestamps.map(
        lambda value: None if value is None or pd.isna(value) else value.timestamp()
    )
    frame["timestamp_label"] = parsed_timestamps.map(
        lambda value: None if value is None or pd.isna(value) else value.isoformat()
    )
    frame["asset"] = frame["asset"].astype(str)
    frame["metric"] = frame["metric"].astype(str).str.upper()
    frame["hover_name"] = frame["hover_name"].fillna(frame["asset"]).astype(str)
    frame["reference_label"] = frame["reference_label"].map(lambda value: None if pd.isna(value) else str(value))
    frame["reference_order"] = pd.to_numeric(frame["reference_order"], errors="coerce")
    reference_order_by_label = {
        label: index
        for index, label in enumerate(
            dict.fromkeys(frame.loc[frame["reference_label"].notna(), "reference_label"].tolist()),
            start=1,
        )
    }
    missing_reference_order = frame["reference_label"].notna() & frame["reference_order"].isna()
    frame.loc[missing_reference_order, "reference_order"] = frame.loc[missing_reference_order, "reference_label"].map(
        reference_order_by_label
    )
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    return frame.loc[:, _NORMALIZED_COLUMNS].dropna(subset=["asset", "metric", "y"])


def _apply_verification_opacity(frame: pd.DataFrame) -> pd.DataFrame:
    """Scale verification marker opacity from oldest to newest timestamp."""
    verification_mask = frame["timestamp_epoch"].notna()
    if not verification_mask.any():
        frame["verification_opacity"] = None
        return frame
    earliest_timestamp = float(frame.loc[verification_mask, "timestamp_epoch"].min())
    latest_timestamp = float(frame.loc[verification_mask, "timestamp_epoch"].max())
    if latest_timestamp <= earliest_timestamp:
        frame["verification_opacity"] = 1.0
        return frame
    frame["verification_opacity"] = None
    normalized = (frame.loc[verification_mask, "timestamp_epoch"] - earliest_timestamp) / (
        latest_timestamp - earliest_timestamp
    )
    frame.loc[verification_mask, "verification_opacity"] = _VERIFICATION_MIN_OPACITY + normalized * (
        1.0 - _VERIFICATION_MIN_OPACITY
    )
    return frame


def _set_line_legend(chart: Line, line_series_names: list[str]) -> None:
    """Restrict the legend to the actual-frequency reference lines."""
    legend = chart.options.get("legend")
    if isinstance(legend, list) and legend and isinstance(legend[0], dict):
        legend[0]["data"] = line_series_names


def _set_legend_only_layout(chart: Line) -> None:
    """Reduce the reserved top margin when the chart title is hidden."""
    grid = chart.options.get("grid")
    if isinstance(grid, list) and grid and isinstance(grid[0], dict):
        grid[0]["top"] = "22%"
        return
    if isinstance(grid, dict):
        grid["top"] = "22%"


def plot_frequency_verification_comparison(data: pd.DataFrame) -> Any:
    """Plot verification markers against actual-frequency reference lines per metric."""
    frame = _normalize_frequency_verification_frame(data)
    if frame.empty:
        raise ValueError("No frequency verification data is available to plot.")

    verification_tooltip = JsCode(
        "function (params) {"
        "  var value = params && params.data ? params.data.value : null;"
        "  if (!Array.isArray(value) || value.length < 4) {"
        "    return params.name;"
        "  }"
        "  return '<strong>' + value[0] + '</strong>'"
        "    + '<br/>Frequency: ' + Number(value[1]).toFixed(4) + ' Hz'"
        "    + '<br/>Timestamp: ' + value[3];"
        "}"
    )
    frequency_tooltip = JsCode(
        "function (params) {"
        "  var rawValue = params && params.data != null ? params.data : params.value;"
        "  if (Array.isArray(rawValue)) {"
        "    rawValue = rawValue.length > 1 ? rawValue[1] : rawValue[0];"
        "  }"
        "  if (rawValue == null || rawValue === '') {"
        "    return params && params.name ? params.name : '';"
        "  }"
        "  return '<strong>' + params.name + '</strong>'"
        "    + '<br/>' + (params.marker || '') + params.seriesName"
        "    + '<br/>Frequency: ' + Number(rawValue).toFixed(4) + ' Hz';"
        "}"
    )

    charts: dict[str, Line] = {}
    for metric, metric_frame in frame.groupby("metric"):
        chart_frame = _apply_verification_opacity(metric_frame.copy())
        chart = Line(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = sorted(chart_frame["asset"].astype(str).unique().tolist())
        chart.add_xaxis(x_values)

        actual_frame = chart_frame.dropna(subset=["reference_label"]).copy()
        line_series_names: list[str] = []
        if not actual_frame.empty:
            reference_order = (
                actual_frame.groupby("reference_label")["reference_order"]
                .min()
                .sort_values(kind="stable")
                .index.tolist()
            )
            for color_index, reference_label in enumerate(reference_order):
                reference_frame = actual_frame[actual_frame["reference_label"] == reference_label].sort_values("asset")
                values_by_asset = {
                    str(row["asset"]): float(row["y"])
                    for row in reference_frame.to_dict(orient="records")
                }
                chart.add_yaxis(
                    str(reference_label),
                    cast(Any, [values_by_asset.get(asset) for asset in x_values]),
                    is_smooth=False,
                    is_symbol_show=True,
                    symbol="circle",
                    symbol_size=_REFERENCE_SYMBOL_SIZE,
                    color=_REFERENCE_LINE_COLORS[color_index % len(_REFERENCE_LINE_COLORS)],
                    tooltip_opts=opts.TooltipOpts(trigger="item", formatter=frequency_tooltip),
                )
                line_series_names.append(str(reference_label))

        verification_frame = chart_frame.dropna(subset=["timestamp_epoch"]).sort_values(["asset", "timestamp_epoch"])
        if not verification_frame.empty:
            scatter = Scatter()
            scatter.add_xaxis(x_values)
            verification_points = [
                {
                    "name": str(row["hover_name"]),
                    "value": [str(row["asset"]), float(row["y"]), str(row["hover_name"]), str(row["timestamp_label"])],
                    "itemStyle": {
                        "color": _VERIFICATION_COLOR,
                        "opacity": float(row["verification_opacity"]),
                    },
                }
                for row in verification_frame.to_dict(orient="records")
            ]
            scatter.add_yaxis(
                "Verification",
                cast(Any, verification_points),
                symbol="circle",
                symbol_size=_VERIFICATION_SYMBOL_SIZE,
                color=_VERIFICATION_COLOR,
                label_opts=_label_opts(is_show=False),
                itemstyle_opts=opts.ItemStyleOpts(color=_VERIFICATION_COLOR),
                tooltip_opts=opts.TooltipOpts(trigger="item", formatter=verification_tooltip),
            )
            chart.overlap(scatter)

        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=opts.TitleOpts(is_show=False),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="item"),
            xaxis_opts=_xaxis_opts(name=""),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _set_line_legend(chart, line_series_names)
        _apply_cartesian_layout(chart)
        _set_legend_only_layout(chart)
        charts[str(metric)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Metric")
