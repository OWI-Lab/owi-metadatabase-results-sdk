"""Plotting strategies for results analyses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast
from uuid import uuid4

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Bar, Geo, Line, Scatter
from pyecharts.globals import CurrentConfig, NotebookType

from .models import PlotRequest, PlotResponse

HTML: Any | None
display: Any | None
widgets: Any | None
try:
    from IPython.display import HTML as _HTML, display as _display
except ImportError:  # pragma: no cover - only used in notebooks.
    HTML = None
    display = None
else:
    HTML = _HTML
    display = _display

try:
    import ipywidgets as _widgets
except ImportError:  # pragma: no cover - only used in notebooks.
    widgets = None
else:
    widgets = _widgets


ChartLike = Any

MONOSPACE_FONT_FAMILY = "monospace"
_TITLE_TOP = "2%"
_LEGEND_TOP = "10%"
_CARTESIAN_GRID = {"top": "24%", "left": "8%", "right": "6%", "bottom": "14%"}


def _text_style_opts(*, font_size: int | None = None, font_weight: str | None = None) -> opts.TextStyleOpts:
    """Return the default monospace text style."""
    kwargs: dict[str, Any] = {"font_family": MONOSPACE_FONT_FAMILY}
    if font_size is not None:
        kwargs["font_size"] = font_size
    if font_weight is not None:
        kwargs["font_weight"] = font_weight
    return opts.TextStyleOpts(**kwargs)


def _label_opts(**kwargs: Any) -> opts.LabelOpts:
    """Return label options using the default monospace font."""
    return opts.LabelOpts(font_family=MONOSPACE_FONT_FAMILY, **kwargs)


def _title_opts(title: str) -> opts.TitleOpts:
    """Return a title configuration that leaves room for the legend."""
    return opts.TitleOpts(
        title=title,
        pos_top=_TITLE_TOP,
        title_textstyle_opts=_text_style_opts(font_size=18, font_weight="bold"),
    )


def _legend_opts() -> opts.LegendOpts:
    """Return a legend configuration separated from the title."""
    return opts.LegendOpts(pos_top=_LEGEND_TOP, textstyle_opts=_text_style_opts())


def _xaxis_opts(*, name: str, rotate: int = 0, boundary_gap: bool | None = None) -> opts.AxisOpts:
    """Return cartesian x-axis options with monospace text."""
    kwargs: dict[str, Any] = {
        "name": name,
        "axislabel_opts": _label_opts(rotate=rotate),
        "name_textstyle_opts": _text_style_opts(),
    }
    if boundary_gap is not None:
        kwargs["boundary_gap"] = boundary_gap
    return opts.AxisOpts(**kwargs)


def _yaxis_opts(*, name: str) -> opts.AxisOpts:
    """Return cartesian y-axis options with monospace text."""
    return opts.AxisOpts(
        name=name,
        axislabel_opts=_label_opts(),
        name_textstyle_opts=_text_style_opts(),
    )


def _tooltip_opts(*, trigger: str, axis_pointer_type: str | None = None) -> opts.TooltipOpts:
    """Return tooltip options with monospace text."""
    kwargs: dict[str, Any] = {"trigger": trigger, "textstyle_opts": _text_style_opts()}
    if axis_pointer_type is not None:
        kwargs["axis_pointer_type"] = axis_pointer_type
    return opts.TooltipOpts(**kwargs)


def _apply_monospace_theme(chart: ChartLike) -> None:
    """Attach a global monospace text style to a chart."""
    text_style = chart.options.get("textStyle")
    if isinstance(text_style, dict):
        text_style.setdefault("fontFamily", MONOSPACE_FONT_FAMILY)
    else:
        chart.options["textStyle"] = {"fontFamily": MONOSPACE_FONT_FAMILY}


def _apply_cartesian_layout(chart: ChartLike) -> None:
    """Reserve chart space so the title and legend do not overlap the plot area."""
    grid = chart.options.get("grid")
    if isinstance(grid, list):
        if grid and isinstance(grid[0], dict):
            grid[0].update(_CARTESIAN_GRID)
        else:
            chart.options["grid"] = [dict(_CARTESIAN_GRID)]
        return
    if isinstance(grid, dict):
        grid.update(_CARTESIAN_GRID)
        return
    chart.options["grid"] = dict(_CARTESIAN_GRID)


def _render_notebook(chart: ChartLike) -> Any:
    """Render a chart using the Jupyter-compatible notebook backend."""
    notebook_type = CurrentConfig.NOTEBOOK_TYPE
    try:
        CurrentConfig.NOTEBOOK_TYPE = NotebookType.JUPYTER_NOTEBOOK
        return chart.render_notebook()
    finally:
        CurrentConfig.NOTEBOOK_TYPE = notebook_type


def _selected_option_suffix(key: str, selected_key: str) -> str:
    """Return the selected HTML attribute suffix for a dropdown option."""
    return ' selected="selected"' if key == selected_key else ""


def _build_widget_dropdown(
    charts_by_key: Mapping[str, ChartLike],
    *,
    dropdown_label: str,
    default_key: str,
) -> Any | None:
    """Build a notebook-native dropdown widget when ipywidgets is available."""
    if widgets is None or display is None:
        return None

    selector = widgets.Dropdown(
        options=list(charts_by_key.keys()),
        value=default_key,
        description=f"{dropdown_label}:",
        layout=widgets.Layout(width="320px"),
    )
    output = widgets.Output()
    style = widgets.HTML(
        value=(
            "<style>"
            ".owi-results-dropdown-widget select,"
            ".owi-results-dropdown-widget label,"
            ".owi-results-dropdown-widget .widget-label {"
            f"font-family:{MONOSPACE_FONT_FAMILY} !important;"
            "}"
            "</style>"
        )
    )

    def render_selected(key: str) -> None:
        with output:
            output.clear_output(wait=True)
            display(_render_notebook(charts_by_key[key]))

    def handle_change(change: dict[str, Any]) -> None:
        if change.get("name") == "value" and change.get("new") is not None:
            render_selected(str(change["new"]))

    selector.observe(handle_change, names="value")
    render_selected(default_key)
    container = widgets.VBox([style, selector, output])
    container.add_class("owi-results-dropdown-widget")
    return container


def _build_nested_widget_dropdown(
    charts_by_primary_key: Mapping[str, Mapping[str, ChartLike]],
    *,
    primary_label: str,
    secondary_label: str,
    default_primary_key: str,
    default_secondary_key: str,
) -> Any | None:
    """Build a notebook-native pair of dependent dropdown widgets."""
    if widgets is None or display is None:
        return None

    primary_selector = widgets.Dropdown(
        options=list(charts_by_primary_key.keys()),
        value=default_primary_key,
        description=f"{primary_label}:",
        layout=widgets.Layout(width="280px"),
    )
    secondary_selector = widgets.Dropdown(
        options=list(charts_by_primary_key[default_primary_key].keys()),
        value=default_secondary_key,
        description=f"{secondary_label}:",
        layout=widgets.Layout(width="280px"),
    )
    output = widgets.Output()
    style = widgets.HTML(
        value=(
            "<style>"
            ".owi-results-dropdown-widget select,"
            ".owi-results-dropdown-widget label,"
            ".owi-results-dropdown-widget .widget-label {"
            f"font-family:{MONOSPACE_FONT_FAMILY} !important;"
            "}"
            "</style>"
        )
    )

    def render_selected(primary_key: str, secondary_key: str) -> None:
        with output:
            output.clear_output(wait=True)
            display(_render_notebook(charts_by_primary_key[primary_key][secondary_key]))

    def handle_primary_change(change: dict[str, Any]) -> None:
        if change.get("name") != "value" or change.get("new") is None:
            return
        selected_primary = str(change["new"])
        secondary_options = list(charts_by_primary_key[selected_primary].keys())
        secondary_selector.options = secondary_options
        if secondary_selector.value not in secondary_options:
            secondary_selector.value = secondary_options[0]
            return
        render_selected(selected_primary, str(secondary_selector.value))

    def handle_secondary_change(change: dict[str, Any]) -> None:
        if change.get("name") == "value" and change.get("new") is not None:
            render_selected(str(primary_selector.value), str(change["new"]))

    primary_selector.observe(handle_primary_change, names="value")
    secondary_selector.observe(handle_secondary_change, names="value")
    render_selected(default_primary_key, default_secondary_key)
    selectors = widgets.HBox([primary_selector, secondary_selector])
    container = widgets.VBox([style, selectors, output])
    container.add_class("owi-results-dropdown-widget")
    return container


def _build_plot_response(chart: ChartLike) -> PlotResponse:
    """Build a response with both embedded HTML and notebook-native output."""
    _apply_monospace_theme(chart)
    dump_with_quotes = getattr(chart, "dump_options_with_quotes", None)
    return PlotResponse(
        chart=chart,
        notebook=_render_notebook(chart),
        html=chart.render_embed(),
        json_options=dump_with_quotes() if callable(dump_with_quotes) else chart.dump_options(),
    )


def build_dropdown_plot_response(
    charts_by_key: Mapping[str, ChartLike],
    *,
    dropdown_label: str,
    default_key: str | None = None,
    height: str = "420px",
) -> PlotResponse:
    """Build an HTML response that switches between chart options via a dropdown."""
    if not charts_by_key:
        raise ValueError("At least one chart is required to build a dropdown plot.")
    selected_key = default_key or next(iter(charts_by_key))
    chart_id = f"owi_results_chart_{uuid4().hex}"
    select_id = f"owi_results_select_{uuid4().hex}"
    render_function = f"render_{chart_id}"
    for _, chart in charts_by_key.items():
        _apply_monospace_theme(chart)
    options_map = "{\n" + ",\n".join(
        f"{json.dumps(key)}: {chart.dump_options()}" for key, chart in charts_by_key.items()
    ) + "\n}"
    option_tags = "".join(
        f'<option value="{key}"{_selected_option_suffix(key, selected_key)}>{key}</option>'
        for key in charts_by_key
    )
    html = f"""
<div class="owi-results-dropdown-plot" style="font-family:{MONOSPACE_FONT_FAMILY}; border-radius: 0.5rem; padding: 1rem; border: 1px solid #ddd;">
    <label for="{select_id}" style="display:block;font-family:{MONOSPACE_FONT_FAMILY};font-weight:600;margin-bottom:8px;">{dropdown_label}</label>
    <select id="{select_id}" style="font-family:{MONOSPACE_FONT_FAMILY};margin-bottom:12px;padding:4px 8px;min-width:160px;">{option_tags}</select>
    <div id="{chart_id}" style="width:100%;height:{height};"></div>
    <script>
        (function() {{
            function loadEcharts(callback) {{
                if (window.echarts) {{
                    callback();
                    return;
                }}
                var existing = document.querySelector('script[data-owi-results-echarts="1"]');
                if (existing) {{
                    existing.addEventListener('load', callback, {{ once: true }});
                    return;
                }}
                var script = document.createElement('script');
                script.src = '{CurrentConfig.ONLINE_HOST}echarts.min.js';
                script.dataset.owiResultsEcharts = '1';
                script.addEventListener('load', callback, {{ once: true }});
                document.head.appendChild(script);
            }}
            loadEcharts(function() {{
                var optionsByKey = {options_map};
                var container = document.getElementById('{chart_id}');
                var selector = document.getElementById('{select_id}');
                var chart = echarts.getInstanceByDom(container) || echarts.init(container);
                function {render_function}(key) {{
                    chart.clear();
                    chart.setOption(optionsByKey[key], true);
                    chart.resize();
                }}
                selector.addEventListener('change', function(event) {{
                    {render_function}(event.target.value);
                }});
                window.addEventListener('resize', function() {{ chart.resize(); }});
                {render_function}({json.dumps(selected_key)});
            }});
        }})();
    </script>
</div>
""".strip()
    notebook = _build_widget_dropdown(charts_by_key, dropdown_label=dropdown_label, default_key=selected_key)
    if notebook is None and HTML is not None:
        notebook = HTML(html)
    return PlotResponse(
        chart=charts_by_key[selected_key],
        notebook=notebook,
        html=html,
        json_options=json.dumps(
            {
                key: json.loads(
                    chart.dump_options_with_quotes()
                    if callable(getattr(chart, "dump_options_with_quotes", None))
                    else chart.dump_options()
                )
                for key, chart in charts_by_key.items()
            }
        ),
    )


def build_nested_dropdown_plot_response(
    charts_by_primary_key: Mapping[str, Mapping[str, ChartLike]],
    *,
    primary_label: str,
    secondary_label: str,
    default_primary_key: str | None = None,
    default_secondary_key: str | None = None,
    height: str = "420px",
) -> PlotResponse:
    """Build an HTML response with dependent primary and secondary dropdowns."""
    if not charts_by_primary_key:
        raise ValueError("At least one chart is required to build a dropdown plot.")
    selected_primary_key = default_primary_key or next(iter(charts_by_primary_key))
    secondary_charts = charts_by_primary_key[selected_primary_key]
    if not secondary_charts:
        raise ValueError("Each primary dropdown option must contain at least one chart.")
    selected_secondary_key = default_secondary_key or next(iter(secondary_charts))
    chart_id = f"owi_results_chart_{uuid4().hex}"
    primary_select_id = f"owi_results_primary_select_{uuid4().hex}"
    secondary_select_id = f"owi_results_secondary_select_{uuid4().hex}"
    render_function = f"render_{chart_id}"
    update_secondary_function = f"updateSecondary_{chart_id}"

    for charts_by_secondary_key in charts_by_primary_key.values():
        for chart in charts_by_secondary_key.values():
            _apply_monospace_theme(chart)

    options_map = "{\n" + ",\n".join(
        f"{json.dumps(primary_key)}: {{\n" + ",\n".join(
            f"{json.dumps(secondary_key)}: {chart.dump_options()}"
            for secondary_key, chart in charts_by_secondary_key.items()
        ) + "\n}"
        for primary_key, charts_by_secondary_key in charts_by_primary_key.items()
    ) + "\n}"
    primary_option_tags = "".join(
        (
            f'<option value="{primary_key}"'
            f'{_selected_option_suffix(primary_key, selected_primary_key)}>{primary_key}</option>'
        )
        for primary_key in charts_by_primary_key
    )
    secondary_option_tags = "".join(
        (
            f'<option value="{secondary_key}"'
            f'{_selected_option_suffix(secondary_key, selected_secondary_key)}>{secondary_key}</option>'
        )
        for secondary_key in secondary_charts
    )
    html = f"""
<div class="owi-results-dropdown-plot" style="font-family:{MONOSPACE_FONT_FAMILY}; border-radius: 0.5rem; padding: 1rem; border: 1px solid #ddd;">
    <div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:12px;">
        <div>
            <label for="{primary_select_id}" style="display:block;font-family:{MONOSPACE_FONT_FAMILY};font-weight:600;margin-bottom:8px;">{primary_label}</label>
            <select id="{primary_select_id}" style="font-family:{MONOSPACE_FONT_FAMILY};padding:4px 8px;min-width:160px;">{primary_option_tags}</select>
        </div>
        <div>
            <label for="{secondary_select_id}" style="display:block;font-family:{MONOSPACE_FONT_FAMILY};font-weight:600;margin-bottom:8px;">{secondary_label}</label>
            <select id="{secondary_select_id}" style="font-family:{MONOSPACE_FONT_FAMILY};padding:4px 8px;min-width:160px;">{secondary_option_tags}</select>
        </div>
    </div>
    <div id="{chart_id}" style="width:100%;height:{height};"></div>
    <script>
        (function() {{
            function loadEcharts(callback) {{
                if (window.echarts) {{
                    callback();
                    return;
                }}
                var existing = document.querySelector('script[data-owi-results-echarts="1"]');
                if (existing) {{
                    existing.addEventListener('load', callback, {{ once: true }});
                    return;
                }}
                var script = document.createElement('script');
                script.src = '{CurrentConfig.ONLINE_HOST}echarts.min.js';
                script.dataset.owiResultsEcharts = '1';
                script.addEventListener('load', callback, {{ once: true }});
                document.head.appendChild(script);
            }}
            loadEcharts(function() {{
                var optionsByPrimaryKey = {options_map};
                var container = document.getElementById('{chart_id}');
                var primarySelector = document.getElementById('{primary_select_id}');
                var secondarySelector = document.getElementById('{secondary_select_id}');
                var chart = echarts.getInstanceByDom(container) || echarts.init(container);
                function {update_secondary_function}(primaryKey, selectedSecondaryKey) {{
                    var secondaryOptions = Object.keys(optionsByPrimaryKey[primaryKey]);
                    secondarySelector.innerHTML = secondaryOptions.map(function(optionKey) {{
                        var selected = optionKey === selectedSecondaryKey ? ' selected="selected"' : '';
                        return '<option value="' + optionKey + '"' + selected + '>' + optionKey + '</option>';
                    }}).join('');
                    if (!secondaryOptions.includes(selectedSecondaryKey)) {{
                        secondarySelector.value = secondaryOptions[0];
                    }}
                }}
                function {render_function}(primaryKey, secondaryKey) {{
                    chart.clear();
                    chart.setOption(optionsByPrimaryKey[primaryKey][secondaryKey], true);
                    chart.resize();
                }}
                primarySelector.addEventListener('change', function(event) {{
                    var primaryKey = event.target.value;
                    {update_secondary_function}(primaryKey, secondarySelector.value);
                    {render_function}(primaryKey, secondarySelector.value);
                }});
                secondarySelector.addEventListener('change', function(event) {{
                    {render_function}(primarySelector.value, event.target.value);
                }});
                window.addEventListener('resize', function() {{ chart.resize(); }});
                {update_secondary_function}({json.dumps(selected_primary_key)}, {json.dumps(selected_secondary_key)});
                {render_function}({json.dumps(selected_primary_key)}, {json.dumps(selected_secondary_key)});
            }});
        }})();
    </script>
</div>
""".strip()
    notebook = _build_nested_widget_dropdown(
        charts_by_primary_key,
        primary_label=primary_label,
        secondary_label=secondary_label,
        default_primary_key=selected_primary_key,
        default_secondary_key=selected_secondary_key,
    )
    if notebook is None and HTML is not None:
        notebook = HTML(html)
    return PlotResponse(
        chart=charts_by_primary_key[selected_primary_key][selected_secondary_key],
        notebook=notebook,
        html=html,
        json_options=json.dumps(
            {
                primary_key: {
                    secondary_key: json.loads(
                        chart.dump_options_with_quotes()
                        if callable(getattr(chart, "dump_options_with_quotes", None))
                        else chart.dump_options()
                    )
                    for secondary_key, chart in charts_by_secondary_key.items()
                }
                for primary_key, charts_by_secondary_key in charts_by_primary_key.items()
            }
        ),
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
            values_by_x = dict(zip(group["x"].astype(str), group["y"], strict=False))
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
