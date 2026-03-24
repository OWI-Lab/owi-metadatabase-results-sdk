"""Dropdown and widget-based chart response builders."""

from __future__ import annotations

import json
from collections.abc import Mapping
from html import escape
from typing import Any, cast
from uuid import uuid4

from pyecharts.datasets import FILENAMES
from pyecharts.globals import CurrentConfig, NotebookType

from ..models import PlotResponse
from .theme import MONOSPACE_FONT_FAMILY, ChartLike, _apply_monospace_theme

HTML: Any | None
display: Any | None
widgets: Any | None

try:
    from IPython.display import HTML as _HTML
    from IPython.display import display as _display
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


def _render_notebook(chart: ChartLike) -> Any:
    """Render a chart using the Jupyter-compatible notebook backend."""
    notebook_type = CurrentConfig.NOTEBOOK_TYPE
    try:
        CurrentConfig.NOTEBOOK_TYPE = NotebookType.JUPYTER_NOTEBOOK
        return chart.render_notebook()
    finally:
        CurrentConfig.NOTEBOOK_TYPE = notebook_type


def _build_widget_dropdown(
    charts_by_key: Mapping[str, ChartLike],
    *,
    dropdown_label: str,
    default_key: str,
) -> Any | None:
    """Build a notebook-native dropdown widget when ipywidgets is available."""
    if widgets is None or display is None:
        return None
    show = cast(Any, display)

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
            ".owi-results-dropdown-widget select {"
            "border-radius:0.25rem !important;"
            "}"
            "</style>"
        )
    )

    def render_selected(key: str) -> None:
        with output:
            output.clear_output(wait=True)
            show(_render_notebook(charts_by_key[key]))

    def handle_change(change: dict[str, Any]) -> None:
        if change.get("name") == "value" and change.get("new") is not None:
            render_selected(str(change["new"]))

    selector.observe(handle_change, names="value")
    container = widgets.VBox([style, selector, output])
    container.add_class("owi-results-dropdown-widget")
    render_selected(default_key)
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
    show = cast(Any, display)

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
            ".owi-results-dropdown-widget select {"
            "border-radius:0.25rem !important;"
            "}"
            "</style>"
        )
    )

    def render_selected(primary_key: str, secondary_key: str) -> None:
        with output:
            output.clear_output(wait=True)
            show(_render_notebook(charts_by_primary_key[primary_key][secondary_key]))

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
    selectors = widgets.HBox([primary_selector, secondary_selector])
    container = widgets.VBox([style, selectors, output])
    container.add_class("owi-results-dropdown-widget")
    render_selected(default_primary_key, default_secondary_key)
    return container


def _initial_render_script(render_expression: str) -> str:
    """Return a resilient initial render script for notebook outputs."""
    return (
        "var renderChart = function() {"
        f"{render_expression};"
        "};"
        "if (typeof requestAnimationFrame === 'function') {"
        "requestAnimationFrame(function() { renderChart(); });"
        "requestAnimationFrame(function() { requestAnimationFrame(function() { renderChart(); }); });"
        "} else {"
        "renderChart();"
        "}"
        "setTimeout(renderChart, 120);"
        "setTimeout(renderChart, 320);"
    )


def _parse_pixel_height(height: str, *, default: int = 420) -> int:
    """Parse a pixel height string into an integer."""
    value = height.strip().lower()
    if value.endswith("px"):
        value = value[:-2]
    try:
        return int(float(value))
    except ValueError:
        return default


def _build_iframe_notebook_html(html: str, *, frame_height: int) -> Any | None:
    """Wrap raw HTML in an iframe so notebook-hosted scripts run reliably."""
    if HTML is None:
        return None
    import warnings

    iframe_resizer = """
<script>
(function() {
    function resizeFrame() {
        if (!window.frameElement) {
            return;
        }
        var body = document.body;
        var html = document.documentElement;
        var height = Math.max(
            body ? body.scrollHeight : 0,
            body ? body.offsetHeight : 0,
            html ? html.scrollHeight : 0,
            html ? html.offsetHeight : 0
        );
        window.frameElement.style.height = height + 'px';
        window.frameElement.height = String(height);
    }
    if (typeof ResizeObserver === 'function') {
        var resizeObserver = new ResizeObserver(resizeFrame);
        resizeObserver.observe(document.documentElement);
        if (document.body) {
            resizeObserver.observe(document.body);
        }
    }
    window.addEventListener('load', resizeFrame);
    window.addEventListener('resize', resizeFrame);
    setTimeout(resizeFrame, 0);
    setTimeout(resizeFrame, 150);
    setTimeout(resizeFrame, 400);
})();
</script>
""".strip()
    escaped_srcdoc = escape(f"{html}\n{iframe_resizer}", quote=True)
    iframe_html = (
        "<iframe "
        'class="owi-results-plot-frame" '
        'sandbox="allow-scripts allow-same-origin" '
        'referrerpolicy="no-referrer" '
        'style="width:100%;border:0;overflow:hidden;" '
        f' height="{frame_height}" '
        f' srcdoc="{escaped_srcdoc}"></iframe>'
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Consider using IPython.display.IFrame instead")
        return HTML(iframe_html)


def _dependency_url(dependency: str) -> str:
    """Return the public asset URL for a pyecharts dependency."""
    parts = FILENAMES.get(dependency)
    if parts is None:
        return f"{CurrentConfig.ONLINE_HOST}{dependency}.js"
    asset_path = "/".join(parts[:-1]) + f".{parts[-1]}"
    return f"{CurrentConfig.ONLINE_HOST}{asset_path}"


def _custom_dropdown_markup(
    *,
    root_id: str,
    label: str,
    items: list[tuple[str, str]],
    selected_value: str,
    min_width: str = "160px",
) -> str:
    """Build the HTML for a custom dropdown button and menu."""
    selected_label = next((item_label for value, item_label in items if value == selected_value), selected_value)
    item_markup = "".join(
        (
            '<button type="button" '
            'class="owi-results-dropdown-item' + (" is-selected" if value == selected_value else "") + '" '
            'data-role="item" '
            f'data-value="{value}" '
            f'data-label="{item_label}" '
            f'aria-pressed="{"true" if value == selected_value else "false"}">{item_label}</button>'
        )
        for value, item_label in items
    )
    return f"""
        <div class="owi-results-control" style="min-width:{min_width};">
            <label for="{root_id}" style="display:block;font-family:{MONOSPACE_FONT_FAMILY};font-weight:600;margin-bottom:8px;">{label}</label>
            <div id="{root_id}" class="owi-results-dropdown" data-value="{selected_value}" data-open="false">
                <button
                    id="{root_id}_toggle"
                    type="button"
                    data-role="toggle"
                    aria-haspopup="menu"
                    aria-expanded="false"
                >
                    <span data-role="label">{selected_label}</span>
                    <span aria-hidden="true">&#9662;</span>
                </button>
                <div data-role="menu" hidden>
                    {item_markup}
                </div>
            </div>
        </div>
    """.strip()


def _dropdown_script_helpers() -> str:
    """Return client-side helpers for the custom dropdown component."""
    return """
                function closeOpenDropdowns(exceptRootId) {
                    document.querySelectorAll('.owi-results-dropdown').forEach(function(root) {
                        if (exceptRootId && root.id === exceptRootId) {
                            return;
                        }
                        root.dataset.open = 'false';
                        var toggle = root.querySelector('[data-role="toggle"]');
                        var menu = root.querySelector('[data-role="menu"]');
                        if (toggle) {
                            toggle.setAttribute('aria-expanded', 'false');
                        }
                        if (menu) {
                            menu.hidden = true;
                        }
                    });
                }

                function escapeHtml(value) {
                    return String(value).replace(/[&<>"']/g, function(character) {
                        return {
                            '&': '&amp;',
                            '<': '&lt;',
                            '>': '&gt;',
                            '"': '&quot;',
                            "'": '&#39;'
                        }[character];
                    });
                }

                function dropdownItemMarkup(item, selectedValue) {
                    var isSelected = item.value === selectedValue;
                    return '<button type="button" class="owi-results-dropdown-item' +
                        (isSelected ? ' is-selected' : '') +
                        '" data-role="item" data-value="' + escapeHtml(item.value) +
                        '" data-label="' + escapeHtml(item.label) +
                        '" aria-pressed="' + (isSelected ? 'true' : 'false') + '">' +
                        escapeHtml(item.label) + '</button>';
                }

                function findSelectedItem(items, value) {
                    for (var index = 0; index < items.length; index += 1) {
                        if (items[index].value === value) {
                            return items[index];
                        }
                    }
                    return items[0] || { value: '', label: '' };
                }

                function createDropdown(rootId, items, selectedValue, onSelect) {
                    var root = document.getElementById(rootId);
                    var toggle = root.querySelector('[data-role="toggle"]');
                    var labelNode = root.querySelector('[data-role="label"]');
                    var menu = root.querySelector('[data-role="menu"]');

                    function syncSelectedState(value) {
                        var selectedItem = findSelectedItem(items, value);
                        root.dataset.value = selectedItem.value;
                        labelNode.textContent = selectedItem.label;
                        menu.querySelectorAll('[data-role="item"]').forEach(function(itemNode) {
                            var isSelected = itemNode.dataset.value === selectedItem.value;
                            itemNode.classList.toggle('is-selected', isSelected);
                            itemNode.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
                        });
                    }

                    function bindItems() {
                        menu.querySelectorAll('[data-role="item"]').forEach(function(itemNode) {
                            itemNode.addEventListener('click', function(event) {
                                event.stopPropagation();
                                syncSelectedState(itemNode.dataset.value);
                                closeOpenDropdowns();
                                onSelect(itemNode.dataset.value);
                            });
                        });
                    }

                    function setItems(nextItems, nextValue) {
                        items = nextItems;
                        var selectedItem = findSelectedItem(items, nextValue);
                        menu.innerHTML = items.map(function(item) {
                            return dropdownItemMarkup(item, selectedItem.value);
                        }).join('');
                        bindItems();
                        syncSelectedState(selectedItem.value);
                    }

                    toggle.addEventListener('click', function(event) {
                        event.stopPropagation();
                        var isOpen = root.dataset.open === 'true';
                        closeOpenDropdowns(root.id);
                        root.dataset.open = isOpen ? 'false' : 'true';
                        toggle.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
                        menu.hidden = isOpen;
                    });

                    setItems(items, selectedValue);

                    return {
                        getValue: function() {
                            return root.dataset.value;
                        },
                        setItems: setItems,
                    };
                }

                document.addEventListener('click', function() {
                    closeOpenDropdowns();
                });
    """.strip()


def _url_loader_script(urls: list[str], callback_name: str, *, loader_name: str = "loadAssetUrls") -> str:
    """Build a script that loads the required asset URLs before rendering."""
    unique_urls = json.dumps(list(dict.fromkeys(urls)))
    return f"""
            function {loader_name}(urls, callback) {{
                if (!urls.length) {{
                    callback();
                    return;
                }}
                var pending = urls.length;
                function onLoaded() {{
                    pending -= 1;
                    if (pending === 0) {{
                        callback();
                    }}
                }}
                urls.forEach(function(url) {{
                    var existingScript = document.querySelector('script[data-owi-results-src="' + url + '"]');
                    if (existingScript) {{
                        if (existingScript.dataset.owiResultsLoaded === 'true') {{
                            onLoaded();
                            return;
                        }}
                        existingScript.addEventListener('load', onLoaded, {{ once: true }});
                        existingScript.addEventListener('error', onLoaded, {{ once: true }});
                        if (url.indexOf('echarts.min.js') !== -1 && !window.echarts) {{
                            return;
                        }}
                        return;
                    }}
                    var script = document.createElement('script');
                    script.src = url;
                    script.dataset.owiResultsSrc = url;
                    script.addEventListener('load', function() {{
                        script.dataset.owiResultsLoaded = 'true';
                        onLoaded();
                    }}, {{ once: true }});
                    script.addEventListener('error', onLoaded, {{ once: true }});
                    document.head.appendChild(script);
                }});
            }}
            {loader_name}({unique_urls}, {callback_name});
""".strip()


def _loader_script(dependencies: list[str], callback_name: str) -> str:
    """Build a script that loads the required chart dependencies before rendering."""
    return _url_loader_script([_dependency_url(dependency) for dependency in dependencies], callback_name)


def _build_plot_response(chart: ChartLike) -> PlotResponse:
    """Build a response with both embedded HTML and notebook-native output."""
    _apply_monospace_theme(chart)
    dump_with_quotes = getattr(chart, "dump_options_with_quotes", None)
    json_options = dump_with_quotes() if callable(dump_with_quotes) else chart.dump_options()
    return PlotResponse(
        chart=chart,
        notebook=_render_notebook(chart),
        html=chart.render_embed(),
        json_options=cast(str, json_options),
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
    load_callback_name = f"renderWhenReady_{chart_id}"
    for _, chart in charts_by_key.items():
        _apply_monospace_theme(chart)
    dependencies = list(
        dict.fromkeys(dependency for chart in charts_by_key.values() for dependency in chart.js_dependencies.items)
    )
    options_map = (
        "{\n" + ",\n".join(f"{json.dumps(key)}: {chart.dump_options()}" for key, chart in charts_by_key.items()) + "\n}"
    )
    key_items = [(key, key) for key in charts_by_key]
    key_dropdown = _custom_dropdown_markup(
        root_id=select_id,
        label=dropdown_label,
        items=key_items,
        selected_value=selected_key,
    )
    html = f"""
<div class="owi-results-dropdown-plot" style="font-family:{MONOSPACE_FONT_FAMILY}; border-radius: 0.5rem; padding: 1rem; border: 1px solid #ddd;">
    <style>
        .owi-results-control {{
            min-width: 160px;
        }}
        .owi-results-dropdown {{
            position: relative;
        }}
        .owi-results-dropdown [data-role="toggle"] {{
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 4px 8px;
            border: 1px solid #d0d0d0;
            border-radius: 0.25rem;
            background: #ffffff;
            color: inherit;
            font-family: {MONOSPACE_FONT_FAMILY};
            cursor: pointer;
        }}
        .owi-results-dropdown [data-role="menu"] {{
            position: absolute;
            top: calc(100% + 4px);
            left: 0;
            z-index: 20;
            min-width: 100%;
            overflow: hidden;
            border: 1px solid #d0d0d0;
            border-radius: 0.25rem;
            background: #ffffff;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
        }}
        .owi-results-dropdown-item {{
            width: 100%;
            display: block;
            padding: 6px 8px;
            border: 0;
            background: transparent;
            color: inherit;
            font-family: {MONOSPACE_FONT_FAMILY};
            text-align: left;
            cursor: pointer;
        }}
        .owi-results-dropdown-item:hover,
        .owi-results-dropdown-item.is-selected {{
            background: #f2f4f7;
        }}
    </style>
    <div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:12px;">
        {key_dropdown}
    </div>
    <div id="{chart_id}" style="width:100%;height:{height};"></div>
    <script>
        (function() {{
            function {load_callback_name}() {{
                var optionsByKey = {options_map};
                var keyItems = {json.dumps([{"value": key, "label": key} for key in charts_by_key])};
                var container = document.getElementById('{chart_id}');
                {_dropdown_script_helpers()}
                var selector = createDropdown('{select_id}', keyItems, {json.dumps(selected_key)}, function(value) {{
                    {render_function}(value);
                }});
                var chart = null;
                function ensureChart() {{
                    if (chart) {{
                        return chart;
                    }}
                    chart = echarts.init(container);
                    return chart;
                }}
                function {render_function}(key) {{
                    var activeChart = ensureChart();
                    activeChart.clear();
                    activeChart.setOption(optionsByKey[key], true);
                    activeChart.resize();
                }}
                window.addEventListener('resize', function() {{ if (chart) {{ chart.resize(); }} }});
                {_initial_render_script(f"{render_function}({json.dumps(selected_key)})")}
            }}
            {_loader_script(dependencies, load_callback_name)}
        }})();
    </script>
</div>
""".strip()
    notebook = _build_iframe_notebook_html(
        html,
        frame_height=_parse_pixel_height(height, default=420) + 90,
    )
    if notebook is None:
        if HTML is not None:
            notebook = HTML(html)
        elif widgets is not None and display is not None:
            notebook = _build_widget_dropdown(
                charts_by_key,
                dropdown_label=dropdown_label,
                default_key=selected_key,
            )
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
    load_callback_name = f"renderWhenReady_{chart_id}"

    for charts_by_secondary_key in charts_by_primary_key.values():
        for chart in charts_by_secondary_key.values():
            _apply_monospace_theme(chart)
    dependencies = list(
        dict.fromkeys(
            dependency
            for charts_by_secondary_key in charts_by_primary_key.values()
            for chart in charts_by_secondary_key.values()
            for dependency in chart.js_dependencies.items
        )
    )

    options_map = (
        "{\n"
        + ",\n".join(
            f"{json.dumps(primary_key)}: {{\n"
            + ",\n".join(
                f"{json.dumps(secondary_key)}: {chart.dump_options()}"
                for secondary_key, chart in charts_by_secondary_key.items()
            )
            + "\n}"
            for primary_key, charts_by_secondary_key in charts_by_primary_key.items()
        )
        + "\n}"
    )
    primary_items = [(primary_key, primary_key) for primary_key in charts_by_primary_key]
    secondary_items_by_primary = {
        primary_key: [(secondary_key, secondary_key) for secondary_key in charts_by_secondary_key]
        for primary_key, charts_by_secondary_key in charts_by_primary_key.items()
    }
    primary_dropdown = _custom_dropdown_markup(
        root_id=primary_select_id,
        label=primary_label,
        items=primary_items,
        selected_value=selected_primary_key,
    )
    secondary_dropdown = _custom_dropdown_markup(
        root_id=secondary_select_id,
        label=secondary_label,
        items=secondary_items_by_primary[selected_primary_key],
        selected_value=selected_secondary_key,
    )
    html = f"""
<div class="owi-results-dropdown-plot" style="font-family:{MONOSPACE_FONT_FAMILY}; border-radius: 0.5rem; padding: 1rem; border: 1px solid #ddd;">
    <style>
        .owi-results-control {{
            min-width: 160px;
        }}
        .owi-results-dropdown {{
            position: relative;
        }}
        .owi-results-dropdown [data-role="toggle"] {{
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 4px 8px;
            border: 1px solid #d0d0d0;
            border-radius: 0.25rem;
            background: #ffffff;
            color: inherit;
            font-family: {MONOSPACE_FONT_FAMILY};
            cursor: pointer;
        }}
        .owi-results-dropdown [data-role="menu"] {{
            position: absolute;
            top: calc(100% + 4px);
            left: 0;
            z-index: 20;
            min-width: 100%;
            overflow: hidden;
            border: 1px solid #d0d0d0;
            border-radius: 0.25rem;
            background: #ffffff;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
        }}
        .owi-results-dropdown-item {{
            width: 100%;
            display: block;
            padding: 6px 8px;
            border: 0;
            background: transparent;
            color: inherit;
            font-family: {MONOSPACE_FONT_FAMILY};
            text-align: left;
            cursor: pointer;
        }}
        .owi-results-dropdown-item:hover,
        .owi-results-dropdown-item.is-selected {{
            background: #f2f4f7;
        }}
    </style>
    <div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:12px;">
        {primary_dropdown}
        {secondary_dropdown}
    </div>
    <div id="{chart_id}" style="width:100%;height:{height};"></div>
    <script>
        (function() {{
            function {load_callback_name}() {{
                var optionsByPrimaryKey = {options_map};
                var primaryItems = {json.dumps([{"value": key, "label": key} for key in charts_by_primary_key])};
                var secondaryItemsByPrimary = {json.dumps({key: [{"value": secondary_key, "label": secondary_key} for secondary_key in charts_by_secondary_key] for key, charts_by_secondary_key in charts_by_primary_key.items()})};
                var container = document.getElementById('{chart_id}');
                {_dropdown_script_helpers()}
                var primarySelector = createDropdown('{primary_select_id}', primaryItems, {json.dumps(selected_primary_key)}, function(primaryKey) {{
                    secondarySelector.setItems(secondaryItemsByPrimary[primaryKey], secondarySelector.getValue());
                    {render_function}(primaryKey, secondarySelector.getValue());
                }});
                var secondarySelector = createDropdown('{secondary_select_id}', secondaryItemsByPrimary[{json.dumps(selected_primary_key)}], {json.dumps(selected_secondary_key)}, function(secondaryKey) {{
                    {render_function}(primarySelector.getValue(), secondaryKey);
                }});
                var chart = null;
                function ensureChart() {{
                    if (chart) {{
                        return chart;
                    }}
                    chart = echarts.init(container);
                    return chart;
                }}
                function resetChart() {{
                    if (chart) {{
                        chart.dispose();
                        chart = null;
                    }}
                }}
                function {render_function}(primaryKey, secondaryKey) {{
                    resetChart();
                    var activeChart = ensureChart();
                    activeChart.clear();
                    activeChart.setOption(optionsByPrimaryKey[primaryKey][secondaryKey], true);
                    activeChart.resize();
                }}
                window.addEventListener('resize', function() {{ if (chart) {{ chart.resize(); }} }});
                {_initial_render_script(f"{render_function}({json.dumps(selected_primary_key)}, {json.dumps(selected_secondary_key)})")}
            }}
            {_loader_script(dependencies, load_callback_name)}
        }})();
    </script>
</div>
""".strip()
    notebook = _build_iframe_notebook_html(
        html,
        frame_height=_parse_pixel_height(height, default=420) + 120,
    )
    if notebook is None:
        if HTML is not None:
            notebook = HTML(html)
        elif widgets is not None and display is not None:
            notebook = _build_nested_widget_dropdown(
                charts_by_primary_key,
                primary_label=primary_label,
                secondary_label=secondary_label,
                default_primary_key=selected_primary_key,
                default_secondary_key=selected_secondary_key,
            )
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
