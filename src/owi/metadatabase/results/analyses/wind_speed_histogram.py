"""Concrete wind speed histogram analysis."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import AnalysisKind, ResultScope, ResultSeries, ResultVector
from ..registry import register_analysis
from .base import BaseAnalysis


class HistogramSeriesInput(BaseModel):
    """Validated input for a single histogram series."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    scope_label: str
    bins: list[tuple[float, float]]
    values: list[float]
    site_id: int | None = None
    location_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_lengths(self) -> HistogramSeriesInput:
        """Require one value per bin."""
        if len(self.bins) != len(self.values):
            raise ValueError("Histogram bins and values must have the same length.")
        return self


class WindSpeedHistogramInput(BaseModel):
    """Validated wind speed histogram request."""

    model_config = ConfigDict(extra="forbid")

    series: list[HistogramSeriesInput] = Field(min_length=1)
    bin_unit: str = "m/s"
    value_unit: str = "count"


@register_analysis
class WindSpeedHistogram(BaseAnalysis):
    """Wind speed histogram analysis."""

    analysis_name = "WindSpeedHistogram"
    analysis_kind = AnalysisKind.HISTOGRAM.value
    result_scope = ResultScope.SITE.value
    default_plot_type = "histogram"

    def validate_inputs(self, payload: Any) -> WindSpeedHistogramInput:
        """Validate histogram request data."""
        if isinstance(payload, WindSpeedHistogramInput):
            return payload
        return WindSpeedHistogramInput.model_validate(payload)

    def compute(self, payload: Any) -> pd.DataFrame:
        """Normalize histogram data to a flat table."""
        validated = self.validate_inputs(payload)
        rows: list[dict[str, Any]] = []
        for series in validated.series:
            point_count = min(len(series.bins), len(series.values))
            for index in range(point_count):
                bin_left, bin_right = series.bins[index]
                value = series.values[index]
                rows.append(
                    {
                        "series_name": series.title,
                        "scope": series.scope_label,
                        "bin_left": bin_left,
                        "bin_right": bin_right,
                        "value": value,
                    }
                )
        return pd.DataFrame(rows)

    def to_results(self, payload: Any) -> list[ResultSeries]:
        """Convert histogram inputs to persisted result series."""
        validated = self.validate_inputs(payload)
        results: list[ResultSeries] = []
        for series in validated.series:
            scope = ResultScope.LOCATION if series.location_id is not None else ResultScope.SITE
            results.append(
                ResultSeries(
                    analysis_name=self.analysis_name,
                    analysis_kind=AnalysisKind.HISTOGRAM,
                    result_scope=scope,
                    short_description=series.title,
                    description=series.description,
                    site_id=series.site_id,
                    location_id=series.location_id,
                    data_additional={
                        "scope_label": series.scope_label,
                        "series_key": series.title,
                        **series.metadata,
                    },
                    vectors=[
                        ResultVector(
                            name="bin_left", unit=validated.bin_unit, values=[left for left, _ in series.bins]
                        ),
                        ResultVector(name="value", unit=validated.value_unit, values=series.values),
                        ResultVector(
                            name="bin_right", unit=validated.bin_unit, values=[right for _, right in series.bins]
                        ),
                    ],
                )
            )
        return results

    def from_results(self, results: Sequence[ResultSeries]) -> pd.DataFrame:
        """Reconstruct normalized histogram rows from stored results."""
        rows: list[dict[str, Any]] = []
        for result in results:
            bin_left = result.vectors[0].values
            values = result.vectors[1].values
            bin_right = result.vectors[2].values if len(result.vectors) > 2 else [None] * len(values)
            point_count = min(len(bin_left), len(values), len(bin_right))
            for index in range(point_count):
                left = bin_left[index]
                value = values[index]
                right = bin_right[index]
                rows.append(
                    {
                        "series_name": result.short_description,
                        "scope": result.data_additional.get("scope_label", result.result_scope.value),
                        "bin_left": left,
                        "bin_right": right,
                        "value": value,
                    }
                )
        return pd.DataFrame(rows)
