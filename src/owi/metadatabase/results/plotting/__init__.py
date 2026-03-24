"""Plotting subpackage for results analyses."""

from .response import (
    build_dropdown_plot_response,
    build_nested_dropdown_plot_response,
)
from .strategies import (
    PLOT_STRATEGIES,
    HistogramPlotStrategy,
    TimeSeriesPlotStrategy,
    get_plot_strategy,
)
from .theme import (
    MONOSPACE_FONT_FAMILY,
    _apply_cartesian_layout,
    _apply_monospace_theme,
    _label_opts,
    _legend_opts,
    _selected_option_suffix,
    _title_opts,
    _tooltip_opts,
    _xaxis_opts,
    _yaxis_opts,
)

__all__ = [
    "MONOSPACE_FONT_FAMILY",
    "PLOT_STRATEGIES",
    "HistogramPlotStrategy",
    "TimeSeriesPlotStrategy",
    "_apply_cartesian_layout",
    "_apply_monospace_theme",
    "_label_opts",
    "_legend_opts",
    "_selected_option_suffix",
    "_title_opts",
    "_tooltip_opts",
    "_xaxis_opts",
    "_yaxis_opts",
    "build_dropdown_plot_response",
    "build_nested_dropdown_plot_response",
    "get_plot_strategy",
]
