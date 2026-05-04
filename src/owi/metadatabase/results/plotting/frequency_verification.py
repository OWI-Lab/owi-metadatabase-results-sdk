"""Plotting helpers for combined frequency and verification comparisons."""

from __future__ import annotations

import json
from collections.abc import Mapping
from math import ceil, sqrt
from typing import Any, cast

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Bar, Line, Scatter
from pyecharts.commons.utils import JsCode

from ..models import ResultQuery
from .definitions import PlotDefinition, PlotSourceData, PlotSourceSpec
from .response import build_dropdown_plot_response
from .theme import (
    _apply_cartesian_interactions,
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
_VERIFICATION_COLOR = "#000000"
_PERMISSABLE_FREQUENCY_KEY = "permissable_frequency"
_PERMISSABLE_BAND_COLOR = "#d62728"
_PERMISSABLE_BAND_OPACITY = 0.35
_PERMISSABLE_BAND_STACK = "__permissable_frequency_band"
_VERIFICATION_MIN_OPACITY = 0.3
_REFERENCE_SYMBOL_SIZE = 5
_VERIFICATION_SYMBOL_SIZE = 8
_DELTA_HISTOGRAM_MAX_BINS = 12
_DELTA_HISTOGRAM_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b", "#17becf")
_DELTA_HISTOGRAM_DECALS = (
    {"symbol": "rect", "dashArrayX": [1, 0], "dashArrayY": [1, 0]},
    {"symbol": "rect", "dashArrayX": [1, 0], "dashArrayY": [4, 2], "rotation": 0.7853981634},
    {"symbol": "rect", "dashArrayX": [1, 0], "dashArrayY": [3, 3]},
    {"symbol": "rect", "dashArrayX": [2, 4], "dashArrayY": [1, 0]},
    {"symbol": "circle", "symbolSize": 1, "dashArrayX": [4, 4], "dashArrayY": [4, 4]},
    {"symbol": "rect", "dashArrayX": [2, 2], "dashArrayY": [2, 2], "rotation": -0.7853981634},
)
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
    "source_url",
    "result_permissable_frequency_lower",
    "result_permissable_frequency_upper",
    "analysis_permissable_frequency_lower",
    "analysis_permissable_frequency_upper",
]
_COMBINED_FREQUENCY_VERIFICATION_COLUMNS = list(_NORMALIZED_COLUMNS)
_DELTA_HISTOGRAM_COLUMNS = [
    "asset",
    "metric",
    "reference_label",
    "reference_order",
    "design_frequency",
    "verification_frequency",
    "timestamp_label",
    "timestamp_epoch",
    "delta_design_frequency_percent",
]


def _require_columns(frame: pd.DataFrame, required_columns: set[str], *, frame_name: str) -> None:
    """Require the given normalized frame columns when the frame is non-empty."""
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"{frame_name} is missing required columns: {missing}.")


def _coerce_optional_int(value: Any) -> int | None:
    """Return an integer for scalar backend identifiers."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_float(value: Any) -> float | None:
    """Return a finite float for scalar limit values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _coerce_mapping(value: Any) -> dict[str, Any]:
    """Return a mapping from raw backend JSON-like values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(decoded) if isinstance(decoded, Mapping) else {}
    return dict(value) if isinstance(value, Mapping) else {}


def _permissable_frequency_pair(additional_data: Mapping[str, Any]) -> tuple[float, float] | None:
    """Return normalized bottom/top frequency limits from metadata."""
    raw_value = additional_data.get(_PERMISSABLE_FREQUENCY_KEY)
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw_value, (list, tuple)) or len(raw_value) < 2:
        return None
    first = _coerce_optional_float(raw_value[0])
    second = _coerce_optional_float(raw_value[1])
    if first is None or second is None:
        return None
    return (min(first, second), max(first, second))


def _source_url_from_analysis_record(record: Mapping[str, Any]) -> str | None:
    """Return a web URL from the parent analysis metadata."""
    for key in ("source_url", "source"):
        value = record.get(key)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        source_url = str(value)
        if source_url:
            return source_url
    return None


def _analysis_metadata_by_id(
    analysis_frame: pd.DataFrame | None,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    """Index parent analysis metadata by backend analysis id."""
    if analysis_frame is None or analysis_frame.empty:
        return {}, None

    metadata_by_id: dict[int, dict[str, Any]] = {}
    metadata_rows: list[dict[str, Any]] = []
    for record in analysis_frame.to_dict(orient="records"):
        additional_data = _coerce_mapping(record.get("additional_data"))
        if not additional_data:
            additional_data = _coerce_mapping(record.get("data_additional"))
        metadata = {
            "additional_data": additional_data,
            "source_url": _source_url_from_analysis_record(record),
        }
        analysis_id = _coerce_optional_int(record.get("id"))
        if analysis_id is None:
            analysis_id = _coerce_optional_int(record.get("analysis_id"))
        if analysis_id is not None:
            metadata_by_id[analysis_id] = metadata
        metadata_rows.append(metadata)
    single_metadata = metadata_rows[0] if len(metadata_rows) == 1 else None
    return metadata_by_id, single_metadata


def _build_plot_source_query(
    query: ResultQuery,
    analysis_name: str,
) -> ResultQuery:
    """Clone the base query for one source analysis."""
    backend_filters = {
        key: value for key, value in query.backend_filters.items() if key not in {"analysis__id", "analysis__name"}
    }
    return query.model_copy(
        update={
            "analysis_name": analysis_name,
            "backend_filters": backend_filters,
        }
    )


def _build_frequency_verification_sources(
    query: ResultQuery,
) -> tuple[PlotSourceSpec, ...]:
    """Return the named sources required by the cross-analysis fleetwide plot."""
    del query
    return (
        PlotSourceSpec(
            key=_FREQUENCY_SOURCE_KEY,
            analysis_name=LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME,
            build_query=lambda source_query, analysis_name=LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME: (
                _build_plot_source_query(source_query, analysis_name)
            ),
        ),
        PlotSourceSpec(
            key=_VERIFICATION_SOURCE_KEY,
            analysis_name=LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME,
            build_query=lambda source_query, analysis_name=LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME: (
                _build_plot_source_query(source_query, analysis_name)
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
    analysis_metadata_by_id, single_analysis_metadata = _analysis_metadata_by_id(
        None if verification_source is None else verification_source.analysis_frame
    )

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
                    "source_url": None,
                    "result_permissable_frequency_lower": None,
                    "result_permissable_frequency_upper": None,
                    "analysis_permissable_frequency_lower": None,
                    "analysis_permissable_frequency_upper": None,
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
            result_additional_data = _coerce_mapping(record.get("result_additional_data"))
            if not result_additional_data:
                result_additional_data = _coerce_mapping(record.get("additional_data"))
            if not result_additional_data:
                result_additional_data = _coerce_mapping(record.get("data_additional"))
            analysis_id = _coerce_optional_int(record.get("analysis_id"))
            analysis_metadata = (
                analysis_metadata_by_id.get(analysis_id) if analysis_id is not None else single_analysis_metadata
            )
            if analysis_metadata is None:
                analysis_metadata = single_analysis_metadata or {}
            result_frequency = _permissable_frequency_pair(result_additional_data)
            analysis_frequency = _permissable_frequency_pair(analysis_metadata.get("additional_data", {}))
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
                    "source_url": analysis_metadata.get("source_url"),
                    "result_permissable_frequency_lower": None if result_frequency is None else result_frequency[0],
                    "result_permissable_frequency_upper": None if result_frequency is None else result_frequency[1],
                    "analysis_permissable_frequency_lower": (
                        None if analysis_frequency is None else analysis_frequency[0]
                    ),
                    "analysis_permissable_frequency_upper": (
                        None if analysis_frequency is None else analysis_frequency[1]
                    ),
                }
            )

    return pd.DataFrame(rows, columns=_COMBINED_FREQUENCY_VERIFICATION_COLUMNS)


def _render_frequency_verification_plot(
    sources_by_key: Mapping[str, PlotSourceData],
    request: Any,
) -> Any:
    """Render the cross-analysis fleetwide frequency/verification plot."""
    del request
    return plot_frequency_verification_comparison(assemble_frequency_verification_comparison_frame(sources_by_key))


def _render_frequency_verification_asset_plot(
    sources_by_key: Mapping[str, PlotSourceData],
    request: Any,
) -> Any:
    """Render the cross-analysis asset frequency/verification plot."""
    del request
    empty_sources = [
        source_key
        for source_key in (_FREQUENCY_SOURCE_KEY, _VERIFICATION_SOURCE_KEY)
        if sources_by_key.get(source_key) is None or sources_by_key[source_key].frame.empty
    ]
    if empty_sources:
        missing = ", ".join(empty_sources)
        raise ValueError(
            f"No frequency verification data is available to plot after filtering. Empty sources: {missing}."
        )
    return plot_frequency_verification_asset_history(assemble_frequency_verification_comparison_frame(sources_by_key))


def assemble_delta_design_frequency_histogram_frame(sources_by_key: Mapping[str, PlotSourceData]) -> pd.DataFrame:
    """Compute latest-verification deltas from frequency and verification sources."""
    frame = assemble_frequency_verification_comparison_frame(sources_by_key)
    if frame.empty:
        return pd.DataFrame(columns=_DELTA_HISTOGRAM_COLUMNS)

    frequency_frame = frame.dropna(subset=["reference_label"]).copy()
    verification_frame = frame.dropna(subset=["timestamp_epoch"]).copy()
    if frequency_frame.empty or verification_frame.empty:
        return pd.DataFrame(columns=_DELTA_HISTOGRAM_COLUMNS)

    design_frame = frequency_frame.loc[
        :,
        ["asset", "metric", "y", "reference_label", "reference_order"],
    ].rename(columns={"y": "design_frequency"})
    latest_index = verification_frame.groupby(["asset", "metric"], sort=False)["timestamp_epoch"].idxmax()
    latest_verification = verification_frame.loc[
        latest_index,
        ["asset", "metric", "y", "timestamp_label", "timestamp_epoch"],
    ].rename(columns={"y": "verification_frequency"})
    delta_frame = design_frame.merge(latest_verification, how="inner", on=["asset", "metric"])
    delta_frame["design_frequency"] = pd.to_numeric(delta_frame["design_frequency"], errors="coerce")
    delta_frame["verification_frequency"] = pd.to_numeric(delta_frame["verification_frequency"], errors="coerce")
    delta_frame = delta_frame.dropna(subset=["design_frequency", "verification_frequency"])
    delta_frame = delta_frame[delta_frame["design_frequency"] != 0].copy()
    if delta_frame.empty:
        return pd.DataFrame(columns=_DELTA_HISTOGRAM_COLUMNS)

    delta_frame["delta_design_frequency_percent"] = (
        (delta_frame["verification_frequency"] - delta_frame["design_frequency"])
        / delta_frame["design_frequency"]
        * 100.0
    )
    delta_frame["reference_order"] = pd.to_numeric(delta_frame["reference_order"], errors="coerce")
    return delta_frame.loc[:, _DELTA_HISTOGRAM_COLUMNS].reset_index(drop=True)


def _render_delta_design_frequency_histogram_plot(
    sources_by_key: Mapping[str, PlotSourceData],
    request: Any,
) -> Any:
    """Render the fleetwide delta design frequency histogram."""
    del request
    return plot_delta_design_frequency_histogram(assemble_delta_design_frequency_histogram_frame(sources_by_key))


def build_frequency_verification_plot_definition() -> PlotDefinition:
    """Return the registered cross-analysis fleetwide frequency/verification plot definition."""
    return PlotDefinition(
        supported_analysis_names=(
            LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME,
            LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME,
        ),
        plot_type="cross_analysis_fleetwide",
        build_sources=_build_frequency_verification_sources,
        render=_render_frequency_verification_plot,
    )


def build_frequency_verification_asset_plot_definition() -> PlotDefinition:
    """Return the registered cross-analysis per-asset frequency/verification plot definition."""
    return PlotDefinition(
        supported_analysis_names=(
            LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME,
            LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME,
        ),
        plot_type="cross_analysis_asset",
        build_sources=_build_frequency_verification_sources,
        render=_render_frequency_verification_asset_plot,
    )


def build_delta_design_frequency_histogram_plot_definition() -> PlotDefinition:
    """Return the registered cross-analysis fleetwide delta histogram definition."""
    return PlotDefinition(
        supported_analysis_names=(
            LIFETIME_DESIGN_FREQUENCIES_ANALYSIS_NAME,
            LIFETIME_DESIGN_VERIFICATION_ANALYSIS_NAME,
        ),
        plot_type="cross_analysis_fleetwide_delta_histogram",
        build_sources=_build_frequency_verification_sources,
        render=_render_delta_design_frequency_histogram_plot,
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

    Expected input is the long-form plotting frame produced by the custom
    cross-analysis plotting layer, not raw backend result rows.
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
    frame["source_url"] = frame["source_url"].map(
        lambda value: None if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
    )
    for column in (
        "result_permissable_frequency_lower",
        "result_permissable_frequency_upper",
        "analysis_permissable_frequency_lower",
        "analysis_permissable_frequency_upper",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
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


def _frequency_band_rows(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Return rows with parsed permissable-frequency limits."""
    lower_column = f"{prefix}_permissable_frequency_lower"
    upper_column = f"{prefix}_permissable_frequency_upper"
    lower_values = pd.to_numeric(frame[lower_column], errors="coerce")
    upper_values = pd.to_numeric(frame[upper_column], errors="coerce")
    band_mask = lower_values.notna() & upper_values.notna()
    if not band_mask.any():
        return pd.DataFrame(columns=["asset", "metric", "lower", "upper"])

    band_frame = frame.loc[band_mask, ["asset", "metric"]].copy()
    band_frame["lower"] = lower_values.loc[band_mask].to_numpy()
    band_frame["upper"] = upper_values.loc[band_mask].to_numpy()
    normalized_lower = band_frame[["lower", "upper"]].min(axis=1)
    normalized_upper = band_frame[["lower", "upper"]].max(axis=1)
    band_frame["lower"] = normalized_lower
    band_frame["upper"] = normalized_upper
    return band_frame.drop_duplicates()


def _single_band_pair(band_frame: pd.DataFrame) -> tuple[float, float] | None:
    """Return the single unique bottom/top pair when one exists."""
    unique_pairs = band_frame.loc[:, ["lower", "upper"]].drop_duplicates()
    if len(unique_pairs) != 1:
        return None
    pair = unique_pairs.iloc[0]
    return (float(pair["lower"]), float(pair["upper"]))


def _resolve_frequency_band_from_prefix(
    frame: pd.DataFrame,
    *,
    metric: str,
    assets: list[str],
    prefix: str,
) -> dict[str, tuple[float, float]]:
    """Resolve permissable-frequency limits for one metadata source."""
    band_frame = _frequency_band_rows(frame, prefix)
    if band_frame.empty:
        return {}

    global_pair = _single_band_pair(band_frame)
    if global_pair is not None:
        return dict.fromkeys(assets, global_pair)

    metric_band_frame = band_frame[band_frame["metric"] == metric]
    if metric_band_frame.empty:
        return {}

    metric_pair = _single_band_pair(metric_band_frame)
    if metric_pair is not None:
        return dict.fromkeys(assets, metric_pair)

    fallback_pair = (float(metric_band_frame["lower"].min()), float(metric_band_frame["upper"].max()))
    asset_pairs = {
        str(asset): (float(asset_frame["lower"].min()), float(asset_frame["upper"].max()))
        for asset, asset_frame in metric_band_frame.groupby("asset", sort=False)
    }
    return {asset: asset_pairs.get(asset, fallback_pair) for asset in assets}


def _resolve_permissable_frequency_band(
    frame: pd.DataFrame,
    *,
    metric: str,
    assets: list[str],
) -> dict[str, tuple[float, float]]:
    """Resolve result-level permissable-frequency limits before analysis-level limits."""
    result_limits = _resolve_frequency_band_from_prefix(frame, metric=metric, assets=assets, prefix="result")
    if result_limits:
        return result_limits

    analysis_band_frame = _frequency_band_rows(frame, "analysis")
    if analysis_band_frame.empty:
        return {}
    analysis_pair = (float(analysis_band_frame["lower"].min()), float(analysis_band_frame["upper"].max()))
    return dict.fromkeys(assets, analysis_pair)


def _add_permissable_frequency_band(
    chart: Line,
    x_values: list[str],
    band_pairs: list[tuple[float, float] | None],
) -> None:
    """Add a filled red permissable-frequency band to a Cartesian line chart."""
    if not any(pair is not None for pair in band_pairs):
        return
    if _global_permissable_frequency_band(band_pairs) is not None:
        return

    lower_values = [None if pair is None else pair[0] for pair in band_pairs]
    height_values = [None if pair is None else pair[1] - pair[0] for pair in band_pairs]
    hidden_tooltip = opts.TooltipOpts(is_show=False)
    band = Bar()
    band.add_xaxis(x_values)
    band.add_yaxis(
        "_Permissable Frequency Lower",
        cast(Any, lower_values),
        stack=_PERMISSABLE_BAND_STACK,
        color=_PERMISSABLE_BAND_COLOR,
        bar_width="92%",
        label_opts=_label_opts(is_show=False),
        itemstyle_opts=opts.ItemStyleOpts(color=_PERMISSABLE_BAND_COLOR, opacity=0),
        tooltip_opts=hidden_tooltip,
        z=0,
    )
    band.add_yaxis(
        "Permissable Frequency Band",
        cast(Any, height_values),
        stack=_PERMISSABLE_BAND_STACK,
        color=_PERMISSABLE_BAND_COLOR,
        bar_width="92%",
        label_opts=_label_opts(is_show=False),
        itemstyle_opts=opts.ItemStyleOpts(color=_PERMISSABLE_BAND_COLOR, opacity=_PERMISSABLE_BAND_OPACITY),
        tooltip_opts=hidden_tooltip,
        z=0,
    )
    chart.overlap(band)


def _global_permissable_frequency_band(
    band_pairs: list[tuple[float, float] | None],
) -> tuple[float, float] | None:
    """Return the single visible band when the current chart has one."""
    unique_pairs = {pair for pair in band_pairs if pair is not None}
    if len(unique_pairs) != 1:
        return None
    return next(iter(unique_pairs))


def _permissable_frequency_mark_area(pair: tuple[float, float]) -> dict[str, Any]:
    """Return an ECharts markArea option for a global frequency band."""
    return opts.MarkAreaOpts(
        is_silent=True,
        label_opts=_label_opts(is_show=False),
        data=[[{"yAxis": pair[0]}, {"yAxis": pair[1]}]],
        itemstyle_opts=opts.ItemStyleOpts(color=_PERMISSABLE_BAND_COLOR, opacity=_PERMISSABLE_BAND_OPACITY),
    ).opts


def _add_global_permissable_frequency_mark_area(
    chart: Line,
    band_pairs: list[tuple[float, float] | None],
) -> None:
    """Attach a global shaded y-band to the first Cartesian series."""
    pair = _global_permissable_frequency_band(band_pairs)
    series = chart.options.get("series")
    if pair is None or not isinstance(series, list) or not series or not isinstance(series[0], dict):
        return
    series[0]["markArea"] = _permissable_frequency_mark_area(pair)


def _add_permissable_frequency_limit_points(
    chart: Line,
    x_values: list[str],
    band_pairs: list[tuple[float, float] | None],
) -> None:
    """Add invisible points so ECharts includes band limits in natural scaling."""
    points: list[dict[str, Any]] = []
    for x_value, pair in zip(x_values, band_pairs, strict=True):
        if pair is None:
            continue
        points.extend(
            [
                {"value": [x_value, pair[0]]},
                {"value": [x_value, pair[1]]},
            ]
        )
    if not points:
        return
    scatter = Scatter()
    scatter.add_xaxis(x_values)
    scatter.add_yaxis(
        "_Permissable Frequency Limits",
        cast(Any, points),
        symbol_size=0,
        label_opts=_label_opts(is_show=False),
        itemstyle_opts=opts.ItemStyleOpts(opacity=0),
        tooltip_opts=opts.TooltipOpts(is_show=False),
    )
    chart.overlap(scatter)


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


def _delta_histogram_bin_edges(values: list[float]) -> list[float]:
    """Return shared histogram bin edges for one metric."""
    if not values:
        return [0.0, 1.0]

    lower = min(values)
    upper = max(values)
    if lower == upper:
        padding = max(abs(lower) * 0.1, 1.0)
        return [lower - padding, upper + padding]

    bin_count = min(_DELTA_HISTOGRAM_MAX_BINS, max(4, ceil(sqrt(len(values)))))
    width = (upper - lower) / bin_count
    return [lower + width * index for index in range(bin_count)] + [upper]


def _delta_histogram_bin_labels(edges: list[float]) -> list[str]:
    """Return readable labels for percentage histogram bins."""
    labels: list[str] = []
    for index in range(len(edges) - 1):
        left = edges[index]
        right = edges[index + 1]
        bracket = "]" if index == len(edges) - 2 else ")"
        labels.append(f"[{left:.1f}, {right:.1f}{bracket}")
    return labels


def _delta_histogram_bin_index(value: float, edges: list[float]) -> int | None:
    """Return the bin index for a value using shared histogram edges."""
    if len(edges) < 2:
        return None
    if value == edges[-1]:
        return len(edges) - 2
    for index in range(len(edges) - 1):
        if edges[index] <= value < edges[index + 1]:
            return index
    return None


def _delta_histogram_counts(values: list[float], edges: list[float]) -> list[int]:
    """Count percentage delta values per histogram bin."""
    counts = [0 for _ in range(max(len(edges) - 1, 0))]
    for value in values:
        bin_index = _delta_histogram_bin_index(value, edges)
        if bin_index is not None:
            counts[bin_index] += 1
    return counts


def _delta_histogram_tooltip() -> JsCode:
    """Return tooltip JS for delta histogram bars."""
    return JsCode(
        "function (params) {"
        "  return '<strong>' + params.seriesName + '</strong>'"
        "    + '<br/>Δ design frequency: ' + params.name"
        "    + '<br/># samples: ' + params.value;"
        "}"
    )


def _delta_histogram_itemstyle(index: int) -> dict[str, Any]:
    """Return color and decal style for one reference-label series."""
    return {
        "color": _DELTA_HISTOGRAM_COLORS[index % len(_DELTA_HISTOGRAM_COLORS)],
        "decal": _DELTA_HISTOGRAM_DECALS[index % len(_DELTA_HISTOGRAM_DECALS)],
    }


def plot_delta_design_frequency_histogram(data: pd.DataFrame) -> Any:
    """Plot fleetwide delta design frequency histograms per metric."""
    if data.empty:
        raise ValueError("No delta design frequency data is available to plot.")

    frame = data.copy()
    frame["metric"] = frame["metric"].astype(str).str.upper()
    frame["reference_label"] = frame["reference_label"].astype(str)
    frame["reference_order"] = pd.to_numeric(frame["reference_order"], errors="coerce")
    frame["delta_design_frequency_percent"] = pd.to_numeric(frame["delta_design_frequency_percent"], errors="coerce")
    frame = frame.dropna(subset=["delta_design_frequency_percent"])
    if frame.empty:
        raise ValueError("No delta design frequency data is available to plot.")

    charts: dict[str, Bar] = {}
    tooltip = _delta_histogram_tooltip()
    for metric, metric_frame in frame.groupby("metric", sort=True):
        values = metric_frame["delta_design_frequency_percent"].astype(float).tolist()
        edges = _delta_histogram_bin_edges(values)
        x_values = _delta_histogram_bin_labels(edges)
        chart = Bar(init_opts=opts.InitOpts(width="100%", height="420px"))
        chart.add_xaxis(x_values)
        reference_order = (
            metric_frame.groupby("reference_label")["reference_order"].min().sort_values(kind="stable").index.tolist()
        )
        for index, reference_label in enumerate(reference_order):
            reference_values = (
                metric_frame.loc[
                    metric_frame["reference_label"] == reference_label,
                    "delta_design_frequency_percent",
                ]
                .astype(float)
                .tolist()
            )
            chart.add_yaxis(
                str(reference_label),
                cast(Any, _delta_histogram_counts(reference_values, edges)),
                category_gap="35%",
                gap="10%",
                label_opts=_label_opts(is_show=False),
                itemstyle_opts=_delta_histogram_itemstyle(index),
                tooltip_opts=opts.TooltipOpts(trigger="item", formatter=tooltip),
            )
        chart.options["aria"] = {"enabled": True, "decal": {"show": True}}
        chart.set_global_opts(
            title_opts=opts.TitleOpts(is_show=False),
            legend_opts=_legend_opts(),
            tooltip_opts=_tooltip_opts(trigger="item"),
            xaxis_opts=_xaxis_opts(name="Δ design frequency [%]"),
            yaxis_opts=_yaxis_opts(name="# samples"),
        )
        _apply_cartesian_layout(chart)
        _set_legend_only_layout(chart)
        _apply_cartesian_interactions(chart)
        charts[str(metric)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Metric")


def _asset_verification_tooltip() -> JsCode:
    """Return verification tooltip JS for asset history plots."""
    return JsCode(
        "function (params) {"
        "  var value = params && params.data ? params.data.value : null;"
        "  if (!Array.isArray(value) || value.length < 4) {"
        "    return params.name;"
        "  }"
        "  function escapeHtml(raw) {"
        '    return String(raw).replace(/[&<>"]/g, function (match) {'
        "      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;'}[match];"
        "    });"
        "  }"
        "  var source = value.length > 4 ? value[4] : null;"
        "  var sourceLine = '';"
        "  var sourceText = source ? String(source) : '';"
        "  if (sourceText) {"
        "    var escapedSource = escapeHtml(sourceText);"
        "    sourceLine = '<br/>Source: <a href=\"' + escapedSource"
        '      + \'" target="_blank" rel="noopener noreferrer">link</a>\';'
        "  }"
        "  return '<strong>' + value[2] + '</strong>'"
        "    + '<br/>Frequency: ' + Number(value[1]).toFixed(4) + ' Hz'"
        "    + '<br/>Timestamp: ' + value[3]"
        "    + sourceLine;"
        "}"
    )


def _asset_frequency_tooltip() -> JsCode:
    """Return frequency-level tooltip JS for asset history plots."""
    return JsCode(
        "function (params) {"
        "  var rawValue = params && params.data != null ? params.data : params.value;"
        "  if (Array.isArray(rawValue)) {"
        "    rawValue = rawValue.length > 1 ? rawValue[1] : rawValue[0];"
        "  }"
        "  if (rawValue == null || rawValue === '') {"
        "    return params && params.name ? params.name : '';"
        "  }"
        "  return '<strong>' + params.seriesName + '</strong>'"
        "    + '<br/>Timestamp: ' + params.name"
        "    + '<br/>Frequency: ' + Number(rawValue).toFixed(4) + ' Hz';"
        "}"
    )


def _build_frequency_verification_asset_chart(
    metric_frame: pd.DataFrame,
    source_frame: pd.DataFrame,
) -> Line | None:
    """Build one asset/metric chart with verification markers and frequency levels."""
    verification_frame = metric_frame.dropna(subset=["timestamp_epoch"]).sort_values("timestamp_epoch")
    if verification_frame.empty:
        return None

    x_values = list(dict.fromkeys(verification_frame["timestamp_label"].astype(str).tolist()))
    chart = Line(init_opts=opts.InitOpts(width="100%", height="420px"))
    chart.add_xaxis(x_values)
    asset_values = sorted(metric_frame["asset"].astype(str).unique().tolist())
    metric_name = str(metric_frame["metric"].iloc[0])
    band_by_asset = _resolve_permissable_frequency_band(source_frame, metric=metric_name, assets=asset_values)
    asset_band = band_by_asset.get(asset_values[0]) if len(asset_values) == 1 else None
    band_pairs = [asset_band for _ in x_values]
    _add_permissable_frequency_band(chart, x_values, band_pairs)

    actual_frame = metric_frame.dropna(subset=["reference_label"]).copy()
    line_series_names: list[str] = []
    if not actual_frame.empty:
        reference_order = (
            actual_frame.groupby("reference_label")["reference_order"].min().sort_values(kind="stable").index.tolist()
        )
        for color_index, reference_label in enumerate(reference_order):
            color = _REFERENCE_LINE_COLORS[color_index % len(_REFERENCE_LINE_COLORS)]
            reference_frame = actual_frame[actual_frame["reference_label"] == reference_label]
            reference_value = float(reference_frame["y"].iloc[0])
            chart.add_yaxis(
                str(reference_label),
                cast(Any, [reference_value for _ in x_values]),
                is_smooth=False,
                is_symbol_show=False,
                color=color,
                linestyle_opts=opts.LineStyleOpts(type_="dashed", color=color),
                tooltip_opts=opts.TooltipOpts(trigger="item", formatter=_asset_frequency_tooltip()),
            )
            line_series_names.append(str(reference_label))

    scatter = Scatter()
    scatter.add_xaxis(x_values)
    verification_points = [
        {
            "name": str(row["hover_name"]),
            "value": [
                str(row["timestamp_label"]),
                float(row["y"]),
                str(row["hover_name"]),
                str(row["timestamp_label"]),
                row["source_url"],
            ],
            "itemStyle": {
                "color": _VERIFICATION_COLOR,
                "opacity": 1.0,
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
        tooltip_opts=opts.TooltipOpts(trigger="item", formatter=_asset_verification_tooltip(), is_enterable=True),
    )
    chart.overlap(scatter)
    _add_global_permissable_frequency_mark_area(chart, band_pairs)
    _add_permissable_frequency_limit_points(chart, x_values, band_pairs)

    chart.set_series_opts(label_opts=_label_opts(is_show=False))
    chart.set_global_opts(
        title_opts=opts.TitleOpts(is_show=False),
        legend_opts=_legend_opts(),
        tooltip_opts=_tooltip_opts(trigger="item"),
        xaxis_opts=_xaxis_opts(name="Datetime", boundary_gap=1 <= len(x_values) <= 3),
        yaxis_opts=_yaxis_opts(name="Frequency [Hz]"),
    )
    _set_line_legend(chart, line_series_names)
    _apply_cartesian_layout(chart)
    _set_legend_only_layout(chart)
    _apply_cartesian_interactions(chart)
    return chart


def plot_frequency_verification_asset_history(data: pd.DataFrame) -> Any:
    """Plot one frequency/verification time history per asset and metric."""
    frame = _normalize_frequency_verification_frame(data)
    if frame.empty:
        raise ValueError("No frequency verification data is available to plot.")

    asset_names = sorted(frame["asset"].dropna().astype(str).unique().tolist())
    if len(asset_names) > 1:
        raise ValueError(
            "cross_analysis_asset expects data for one asset. "
            f"Filter to a single location or turbine; found: {', '.join(asset_names)}."
        )

    charts_by_metric: dict[str, Line] = {}
    for metric, metric_frame in frame.groupby("metric", sort=True):
        chart = _build_frequency_verification_asset_chart(
            metric_frame.copy(),
            frame,
        )
        if chart is not None:
            charts_by_metric[str(metric)] = chart

    if not charts_by_metric:
        raise ValueError("No dated verification data is available to plot.")

    return build_dropdown_plot_response(charts_by_metric, dropdown_label="Metric")


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
        "  function escapeHtml(raw) {"
        '    return String(raw).replace(/[&<>"]/g, function (match) {'
        "      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;'}[match];"
        "    });"
        "  }"
        "  var source = value.length > 4 ? value[4] : null;"
        "  var sourceLine = '';"
        "  var sourceText = source ? String(source) : '';"
        "  if (sourceText) {"
        "    var escapedSource = escapeHtml(sourceText);"
        "    sourceLine = '<br/>Source: <a href=\"' + escapedSource"
        '      + \'" target="_blank" rel="noopener noreferrer">link</a>\';'
        "  }"
        "  return '<strong>' + value[0] + '</strong>'"
        "    + '<br/>Frequency: ' + Number(value[1]).toFixed(4) + ' Hz'"
        "    + '<br/>Timestamp: ' + value[3]"
        "    + sourceLine;"
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
        band_by_asset = _resolve_permissable_frequency_band(frame, metric=str(metric), assets=x_values)
        band_pairs = [band_by_asset.get(asset) for asset in x_values]
        _add_permissable_frequency_band(chart, x_values, band_pairs)

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
                    str(row["asset"]): float(row["y"]) for row in reference_frame.to_dict(orient="records")
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
                    "value": [
                        str(row["asset"]),
                        float(row["y"]),
                        str(row["hover_name"]),
                        str(row["timestamp_label"]),
                        row["source_url"],
                    ],
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
                tooltip_opts=opts.TooltipOpts(trigger="item", formatter=verification_tooltip, is_enterable=True),
            )
            chart.overlap(scatter)
        _add_global_permissable_frequency_mark_area(chart, band_pairs)
        _add_permissable_frequency_limit_points(chart, x_values, band_pairs)

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
        _apply_cartesian_interactions(chart)
        charts[str(metric)] = chart
    return build_dropdown_plot_response(charts, dropdown_label="Metric")
