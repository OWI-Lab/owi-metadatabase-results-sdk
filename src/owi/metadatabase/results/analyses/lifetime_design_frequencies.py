"""Concrete lifetime design frequencies comparison analysis."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ..models import AnalysisKind, ResultScope, ResultSeries, ResultVector
from ..registry import register_analysis
from .base import BaseAnalysis


class FrequencyRow(BaseModel):
    """Validated row for the lifetime design frequencies analysis."""

    model_config = ConfigDict(extra="forbid")

    turbine: str
    reference: str
    fa1: float | None = Field(default=None, alias="FA1")
    ss1: float | None = Field(default=None, alias="SS1")
    fa2: float | None = Field(default=None, alias="FA2")
    ss2: float | None = Field(default=None, alias="SS2")
    location_id: int | None = None
    site_id: int | None = None


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

    metric_columns = ("fa1", "ss1", "fa2", "ss2")

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
            for metric in self.metric_columns:
                value = getattr(row, metric)
                if value is None:
                    continue
                rows.append(
                    {
                        "x": row.reference,
                        "y": value,
                        "series_name": f"{row.turbine} - {metric.upper()}",
                        "turbine": row.turbine,
                        "metric": metric.upper(),
                        "reference": row.reference,
                    }
                )
        return pd.DataFrame(rows)

    def to_results(self, payload: Any) -> list[ResultSeries]:
        """Convert design frequency rows to persisted result series."""
        validated = self.validate_inputs(payload)
        grouped: dict[tuple[str, str, int | None, int | None], list[FrequencyRow]] = {}
        for row in validated.rows:
            for metric in self.metric_columns:
                if getattr(row, metric) is None:
                    continue
                key = (row.turbine, metric.upper(), row.site_id, row.location_id)
                grouped.setdefault(key, []).append(row)
        results: list[ResultSeries] = []
        for (turbine, metric, site_id, location_id), rows in grouped.items():
            ordered_rows = list(rows)
            x_labels = [item.reference for item in ordered_rows]
            x_indices = [float(index) for index, _ in enumerate(ordered_rows)]
            y_values = [float(getattr(item, metric.lower())) for item in ordered_rows]
            results.append(
                ResultSeries(
                    analysis_name=self.analysis_name,
                    analysis_kind=AnalysisKind.COMPARISON,
                    result_scope=ResultScope.LOCATION if location_id is not None else ResultScope.SITE,
                    short_description=f"{turbine} - {metric}",
                    site_id=site_id,
                    location_id=location_id,
                    data_additional={
                        "turbine": turbine,
                        "metric": metric,
                        "reference_labels": x_labels,
                        "series_key": f"{turbine}:{metric}",
                    },
                    vectors=[
                        ResultVector(name="reference_index", unit="index", values=x_indices),
                        ResultVector(name=metric.lower(), unit="Hz", values=y_values),
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
            labels = result.data_additional.get("reference_labels", [])
            for index, (x_value, y_value) in enumerate(zip(x_values, y_values, strict=False)):
                label = labels[index] if index < len(labels) else str(x_value)
                rows.append(
                    {
                        "x": label,
                        "y": y_value,
                        "series_name": result.short_description,
                        "turbine": result.data_additional.get("turbine", result.short_description),
                        "metric": result.data_additional.get("metric", result.vectors[1].name.upper()),
                        "reference": label,
                    }
                )
        return pd.DataFrame(rows)
