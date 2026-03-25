"""Concrete plot rendering strategies."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Bar, Line

from ..models import PlotRequest, PlotResponse
from .response import _build_plot_response
from .theme import (
    _apply_cartesian_layout,
    _label_opts,
    _legend_opts,
    _title_opts,
    _tooltip_opts,
    _xaxis_opts,
    _yaxis_opts,
)


class HistogramPlotStrategy:
    """Render histogram-like analyses with pyecharts bar charts."""

    chart_type = "histogram"

    def render(self, data: pd.DataFrame, request: PlotRequest) -> PlotResponse:
        """Render a histogram chart from normalized data."""
        frame = data.copy()
        frame["bin_label"] = frame.apply(
            lambda row: (
                f"[{row['bin_left']},{row['bin_right']})" if pd.notna(row.get("bin_right")) else str(row["bin_left"])
            ),
            axis=1,
        )
        chart = Bar(init_opts=opts.InitOpts(width="100%", height="420px"))
        labels = list(dict.fromkeys(frame["bin_label"].tolist()))
        chart.add_xaxis(labels)
        for series_name, group in frame.groupby("series_name"):
            values_by_label = dict(group[["bin_label", "value"]].itertuples(index=False, name=None))
            chart.add_yaxis(
                str(series_name),
                [float(values_by_label.get(label, 0.0)) for label in labels],
                category_gap="30%",
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(request.title or request.analysis_name),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="axis", axis_pointer_type="shadow"),
            xaxis_opts=_xaxis_opts(name="Bin"),
            yaxis_opts=_yaxis_opts(name="Value"),
        )
        _apply_cartesian_layout(chart)
        return _build_plot_response(chart)


class TimeSeriesPlotStrategy:
    """Render time-series analyses with pyecharts line charts."""

    chart_type = "time_series"

    def render(self, data: pd.DataFrame, request: PlotRequest) -> PlotResponse:
        """Render a time-series chart from normalized data."""
        frame = data.copy()
        chart = Line(init_opts=opts.InitOpts(width="100%", height="420px"))
        x_values = list(dict.fromkeys(frame["x"].astype(str).tolist()))
        chart.add_xaxis(x_values)
        for series_name, group in frame.groupby("series_name"):
            values_by_x = {
                str(x_value): y_value for x_value, y_value in group[["x", "y"]].itertuples(index=False, name=None)
            }
            chart.add_yaxis(
                str(series_name),
                cast(Any, [float(values_by_x.get(value, 0.0)) for value in x_values]),
                is_smooth=False,
                is_symbol_show=True,
                symbol_size=6,
            )
        chart.set_series_opts(label_opts=_label_opts(is_show=False))
        chart.set_global_opts(
            title_opts=_title_opts(request.title or request.analysis_name),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="axis"),
            xaxis_opts=_xaxis_opts(name="Time / Axis", boundary_gap=False),
            yaxis_opts=_yaxis_opts(name="Value"),
        )
        _apply_cartesian_layout(chart)
        return _build_plot_response(chart)


PLOT_STRATEGIES = {
    "histogram": HistogramPlotStrategy(),
    "time_series": TimeSeriesPlotStrategy(),
    "comparison": TimeSeriesPlotStrategy(),
}


def get_plot_strategy(plot_type: str):
    """Return the plotting strategy for a given plot type."""
    return PLOT_STRATEGIES[plot_type]
