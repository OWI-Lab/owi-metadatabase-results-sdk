"""Plotting strategies for results analyses."""

from __future__ import annotations

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Bar, Line
from pyecharts.globals import CurrentConfig, NotebookType

from .models import PlotRequest, PlotResponse


def _build_plot_response(chart: Bar | Line) -> PlotResponse:
    """Build a response with both embedded HTML and notebook-native output."""
    notebook_type = CurrentConfig.NOTEBOOK_TYPE
    try:
        CurrentConfig.NOTEBOOK_TYPE = NotebookType.JUPYTER_NOTEBOOK
        notebook = chart.render_notebook()
    finally:
        CurrentConfig.NOTEBOOK_TYPE = notebook_type
    return PlotResponse(
        chart=chart,
        notebook=notebook,
        html=chart.render_embed(),
        json_options=chart.dump_options(),
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
            values_by_label = dict(zip(group["bin_label"], group["value"], strict=False))
            chart.add_yaxis(
                str(series_name),
                [float(values_by_label.get(label, 0.0)) for label in labels],
                category_gap="30%",
            )
        chart.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
        chart.set_global_opts(
            title_opts=opts.TitleOpts(title=request.title or request.analysis_name),
            legend_opts=opts.LegendOpts(pos_top="5%"),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="shadow"),
            xaxis_opts=opts.AxisOpts(name="Bin", axislabel_opts=opts.LabelOpts(rotate=0)),
            yaxis_opts=opts.AxisOpts(name="Value"),
        )
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
            values_by_x = dict(zip(group["x"].astype(str), group["y"], strict=False))
            chart.add_yaxis(
                str(series_name),
                [float(values_by_x.get(value, 0.0)) for value in x_values],
                is_smooth=False,
                is_symbol_show=True,
                symbol_size=6,
            )
        chart.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
        chart.set_global_opts(
            title_opts=opts.TitleOpts(title=request.title or request.analysis_name),
            legend_opts=opts.LegendOpts(pos_top="5%"),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
            xaxis_opts=opts.AxisOpts(name="Time / Axis", type_="category", boundary_gap=False),
            yaxis_opts=opts.AxisOpts(name="Value"),
        )
        return _build_plot_response(chart)


PLOT_STRATEGIES = {
    "histogram": HistogramPlotStrategy(),
    "time_series": TimeSeriesPlotStrategy(),
    "comparison": TimeSeriesPlotStrategy(),
}


def get_plot_strategy(plot_type: str):
    """Return the plotting strategy for a given plot type."""
    return PLOT_STRATEGIES[plot_type]
