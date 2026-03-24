"""Theme constants and chart styling helpers."""

from __future__ import annotations

from typing import Any

from pyecharts import options as opts

ChartLike = Any

MONOSPACE_FONT_FAMILY = "monospace"
_TITLE_TOP = "2%"
_LEGEND_TOP = "10%"
_CARTESIAN_GRID = {"top": "30%", "left": "8%", "right": "6%", "bottom": "14%"}


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
    return opts.LegendOpts(type_="scroll", pos_top=_LEGEND_TOP, textstyle_opts=_text_style_opts())


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


def _selected_option_suffix(key: str, selected_key: str) -> str:
    """Return the selected HTML attribute suffix for a dropdown option."""
    return ' selected="selected"' if key == selected_key else ""
