"""Concrete lifetime design frequencies comparison analysis."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ..models import AnalysisKind, PlotRequest, PlotResponse, ResultScope, ResultSeries, ResultVector
from ..plotting.frequency import (
    plot_lifetime_design_frequencies_by_location,
    plot_lifetime_design_frequencies_comparison,
    plot_lifetime_design_frequencies_geo,
)
from ..registry import register_analysis
from .base import BaseAnalysis


class FrequencyRow(BaseModel):
    """Validated row for the lifetime design frequencies analysis."""

    model_config = ConfigDict(extra="allow")

    legacy_metric_fields: ClassVar[tuple[str, ...]] = ("fa1", "ss1", "fa2", "ss2")

    turbine: str
    reference: str
    fa1: float | None = Field(default=None, alias="FA1")
    ss1: float | None = Field(default=None, alias="SS1")
    fa2: float | None = Field(default=None, alias="FA2")
    ss2: float | None = Field(default=None, alias="SS2")
    location_id: int | None = None
    site_id: int | None = None

    @staticmethod
    def _normalize_metric_name(metric_name: str) -> str:
        """Normalize a metric label used in notebook and workbook inputs."""
        normalized = metric_name.strip().upper()
        if not normalized:
            raise ValueError("Metric names cannot be empty.")
        return normalized

    def metric_values(self) -> dict[str, float]:
        """Return all non-null metric values, including dynamic optional metrics."""
        metrics: dict[str, float] = {}
        for field_name in self.legacy_metric_fields:
            value = getattr(self, field_name)
            if value is None:
                continue
            alias = type(self).model_fields[field_name].alias or field_name.upper()
            metrics[self._normalize_metric_name(alias)] = float(value)

        for raw_name, raw_value in (self.model_extra or {}).items():
            metric_name = self._normalize_metric_name(str(raw_name))
            if metric_name in metrics:
                raise ValueError(f"Duplicate metric name after normalization: {metric_name}.")
            if raw_value is None:
                continue
            metrics[metric_name] = float(raw_value)
        return metrics

    @property
    def metric_names(self) -> list[str]:
        """Return the normalized metric labels available on this row."""
        return list(self.metric_values().keys())

    def model_post_init(self, __context: Any) -> None:
        """Validate legacy and dynamic metric values after model construction."""
        del __context
        self.metric_values()


class LifetimeDesignFrequenciesInput(BaseModel):
    """Validated input for the design frequencies analysis."""

    model_config = ConfigDict(extra="forbid")

    rows: list[FrequencyRow] = Field(min_length=1)


@register_analysis
class LifetimeDesignFrequencies(BaseAnalysis):
    """Comparison analysis for design frequencies by turbine and reference."""

    analysis_name = "LifetimeDesignFrequencies"
    analysis_kind = AnalysisKind.COMPARISON.value
    result_scope = ResultScope.LOCATION.value
    default_plot_type = "comparison"

    reference_labels_key = "reference_labels"

    def validate_inputs(self, payload: Any) -> LifetimeDesignFrequenciesInput:
        """Validate frequency comparison request data."""
        if isinstance(payload, LifetimeDesignFrequenciesInput):
            return payload
        return LifetimeDesignFrequenciesInput.model_validate(payload)

    def compute(self, payload: Any) -> pd.DataFrame:
        """Normalize comparison input rows into a long table."""
        validated = self.validate_inputs(payload)
        rows: list[dict[str, Any]] = []
        for row in validated.rows:
            for metric, value in row.metric_values().items():
                rows.append(
                    {
                        "x": row.reference,
                        "y": value,
                        "series_name": f"{row.turbine} - {metric}",
                        "turbine": row.turbine,
                        "metric": metric,
                        "reference": row.reference,
                        "location_id": row.location_id,
                        "site_id": row.site_id,
                    }
                )
        return pd.DataFrame(rows)

    @staticmethod
    def _split_series_description(short_description: str) -> tuple[str, str | None]:
        """Split the persisted short description into turbine and metric parts."""
        if " - " not in short_description:
            return short_description, None
        turbine, metric = short_description.rsplit(" - ", 1)
        return turbine, metric

    def to_results(self, payload: Any) -> list[ResultSeries]:
        """Convert design frequency rows to persisted result series."""
        validated = self.validate_inputs(payload)
        grouped: dict[tuple[str, str, int | None, int | None], list[tuple[str, float]]] = {}
        for row in validated.rows:
            for metric, value in row.metric_values().items():
                key = (row.turbine, metric, row.site_id, row.location_id)
                grouped.setdefault(key, []).append((str(row.reference), value))
        results: list[ResultSeries] = []
        for (turbine, metric, site_id, location_id), rows in grouped.items():
            x_labels = [reference for reference, _ in rows]
            x_indices = [float(index) for index, _ in enumerate(rows)]
            y_values = [value for _, value in rows]
            results.append(
                ResultSeries(
                    analysis_name=self.analysis_name,
                    analysis_kind=AnalysisKind.COMPARISON,
                    result_scope=ResultScope.LOCATION if location_id is not None else ResultScope.SITE,
                    short_description=f"{turbine} - {metric}",
                    site_id=site_id,
                    location_id=location_id,
                    data_additional={
                        self.reference_labels_key: x_labels,
                    },
                    vectors=[
                        ResultVector(name="reference_index", unit="index", values=x_indices),
                        ResultVector(name=metric, unit="Hz", values=y_values),
                    ],
                )
            )
        return results

    def from_results(self, results: Sequence[ResultSeries]) -> pd.DataFrame:
        """Reconstruct normalized comparison rows from stored results."""
        rows: list[dict[str, Any]] = []
        for result in results:
            x_values = result.vectors[0].values
            y_values = result.vectors[1].values
            labels = self._reference_labels_from_result(result)
            turbine, metric = self._split_series_description(result.short_description)
            for index, (x_value, y_value) in enumerate(zip(x_values, y_values, strict=False)):
                label = labels[index] if index < len(labels) else str(x_value)
                rows.append(
                    {
                        "x": label,
                        "y": y_value,
                        "series_name": result.short_description,
                        "turbine": turbine,
                        "metric": metric or result.vectors[1].name,
                        "reference": label,
                        "location_id": result.location_id,
                        "site_id": result.site_id,
                    }
                )
        return pd.DataFrame(rows)

    def _reference_labels_from_result(self, result: ResultSeries) -> list[str]:
        """Return the per-point reference labels stored in result metadata."""
        value = result.data_additional.get(self.reference_labels_key, [])
        if isinstance(value, str):
            return [value]
        if isinstance(value, Sequence):
            return [str(item) for item in value]
        return []

    def plot(
        self,
        results: Sequence[ResultSeries],
        request: PlotRequest | None = None,
        plot_strategy: Any | None = None,
    ) -> PlotResponse:
        """Render frequencies using the requested plot type."""
        del plot_strategy
        plot_request = request or PlotRequest(analysis_name=self.analysis_name)
        plot_type = plot_request.plot_type or "location"
        location_frame = plot_request.context.get("location_frame")
        data = self.from_results(results)

        if plot_type == "comparison":
            return plot_lifetime_design_frequencies_comparison(data, location_frame=location_frame)
        if plot_type == "location":
            return plot_lifetime_design_frequencies_by_location(data, location_frame=location_frame)
        if plot_type in {"geo", "map"}:
            if not isinstance(location_frame, pd.DataFrame) or location_frame.empty:
                raise ValueError("Location coordinates are required for the geo lifetime design frequency plot.")
            return plot_lifetime_design_frequencies_geo(data, location_frame=location_frame)
        raise ValueError(f"Unsupported plot_type for {self.analysis_name}: {plot_type}")
