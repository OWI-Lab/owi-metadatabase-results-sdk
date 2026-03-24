"""Plotting helpers for lifetime design verification analyses."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Line

from .response import build_dropdown_plot_response
from .theme import (
    _apply_cartesian_layout,
    _label_opts,
    _legend_opts,
    _title_opts,
    _tooltip_opts,
    _xaxis_opts,
    _yaxis_opts,
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
            values_by_x = dict(zip(turbine_frame["x"].astype(str), turbine_frame["y"], strict=False))
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
            xaxis_opts=_xaxis_opts(name="Timestamp", boundary_gap=False),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _apply_cartesian_layout(chart)
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
            values_by_x = dict(zip(metric_frame["x"].astype(str), metric_frame["y"], strict=False))
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
            xaxis_opts=_xaxis_opts(name="Timestamp", boundary_gap=False),
            yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
        )
        _apply_cartesian_layout(chart)
        charts[str(turbine)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Turbine")
