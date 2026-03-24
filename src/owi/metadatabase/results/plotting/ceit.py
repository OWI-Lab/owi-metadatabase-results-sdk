"""CEIT sensor measurement plotting."""

from __future__ import annotations

from collections.abc import Sequence
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


def plot_ceit_analyses(data: pd.DataFrame | Sequence[Any]) -> Any:
    """Plot CEIT sensor measurements with a dropdown that switches sensors."""
    from ..analyses.ceit import ceit_frame_from_measurements

    frame = ceit_frame_from_measurements(data) if not isinstance(data, pd.DataFrame) else data.copy()
    if frame.empty:
        raise ValueError("No CEIT measurements are available to plot.")
    charts: dict[str, Line] = {}
    for sensor_identifier, sensor_frame in frame.groupby("sensor_identifier"):
        chart = Line(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = list(dict.fromkeys(sensor_frame["timestamp"].astype(str).tolist()))
        chart.add_xaxis(x_values)
        for metric, metric_frame in sensor_frame.groupby("metric"):
            values_by_timestamp = dict(zip(metric_frame["timestamp"].astype(str), metric_frame["value"], strict=False))
            chart.add_yaxis(
                str(metric),
                cast(Any, [values_by_timestamp.get(timestamp) for timestamp in x_values]),
                is_smooth=False,
                is_symbol_show=True,
                symbol_size=6,
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(f"CEIT Sensor {sensor_identifier}"),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="axis"),
            xaxis_opts=_xaxis_opts(name="Timestamp", boundary_gap=False),
            yaxis_opts=_yaxis_opts(name="Value"),
        )
        _apply_cartesian_layout(chart)
        charts[str(sensor_identifier)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Sensor")
