"""Concrete lifetime design verification analysis."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import AnalysisKind, ResultScope, ResultSeries, ResultVector
from ..registry import register_analysis
from .base import BaseAnalysis


class VerificationRow(BaseModel):
    """Validated row for the lifetime verification analysis."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    turbine: str
    fa1: float | None = Field(default=None, alias="FA1")
    ss1: float | None = Field(default=None, alias="SS1")
    ss2: float | None = Field(default=None, alias="SS2")
    fa2: float | None = Field(default=None, alias="FA2")
    location_id: int | None = None
    site_id: int | None = None

    @field_validator("timestamp")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        """Require timezone-aware timestamps."""
        if value.tzinfo is None:
            raise ValueError("Verification timestamps must be timezone-aware.")
        return value


class LifetimeDesignVerificationInput(BaseModel):
    """Validated input for the verification analysis."""

    model_config = ConfigDict(extra="forbid")

    rows: list[VerificationRow] = Field(min_length=1)


@register_analysis
class LifetimeDesignVerification(BaseAnalysis):
    """Lifetime design verification time-series analysis."""

    analysis_name = "LifetimeDesignVerification"
    analysis_kind = AnalysisKind.TIME_SERIES.value
    result_scope = ResultScope.LOCATION.value
    default_plot_type = "time_series"

    metric_columns = ("fa1", "ss1", "ss2", "fa2")

    def validate_inputs(self, payload: Any) -> LifetimeDesignVerificationInput:
        """Validate verification request data."""
        if isinstance(payload, LifetimeDesignVerificationInput):
            return payload
        return LifetimeDesignVerificationInput.model_validate(payload)

    def compute(self, payload: Any) -> pd.DataFrame:
        """Normalize verification input rows into a long table."""
        validated = self.validate_inputs(payload)
        rows: list[dict[str, Any]] = []
        for row in validated.rows:
            for metric in self.metric_columns:
                value = getattr(row, metric)
                if value is None:
                    continue
                rows.append(
                    {
                        "x": row.timestamp.isoformat(),
                        "y": value,
                        "series_name": f"{row.turbine} - {metric.upper()}",
                        "turbine": row.turbine,
                        "metric": metric.upper(),
                    }
                )
        return pd.DataFrame(rows)

    def to_results(self, payload: Any) -> list[ResultSeries]:
        """Convert verification rows to persisted result series."""
        validated = self.validate_inputs(payload)
        grouped: dict[tuple[str, str, int | None, int | None], list[VerificationRow]] = {}
        for row in validated.rows:
            for metric in self.metric_columns:
                if getattr(row, metric) is None:
                    continue
                key = (row.turbine, metric.upper(), row.site_id, row.location_id)
                grouped.setdefault(key, []).append(row)
        results: list[ResultSeries] = []
        for (turbine, metric, site_id, location_id), rows in grouped.items():
            ordered_rows = sorted(rows, key=lambda item: item.timestamp)
            epoch_values = [item.timestamp.astimezone(timezone.utc).timestamp() for item in ordered_rows]
            metric_values = [float(getattr(item, metric.lower())) for item in ordered_rows]
            results.append(
                ResultSeries(
                    analysis_name=self.analysis_name,
                    analysis_kind=AnalysisKind.TIME_SERIES,
                    result_scope=ResultScope.LOCATION if location_id is not None else ResultScope.SITE,
                    short_description=f"{turbine} - {metric}",
                    site_id=site_id,
                    location_id=location_id,
                    data_additional={"turbine": turbine, "metric": metric, "series_key": f"{turbine}:{metric}"},
                    vectors=[
                        ResultVector(name="timestamp", unit="s", values=epoch_values),
                        ResultVector(name=metric.lower(), unit="Hz", values=metric_values),
                    ],
                )
            )
        return results

    def from_results(self, results: Sequence[ResultSeries]) -> pd.DataFrame:
        """Reconstruct normalized time-series rows from stored results."""
        rows: list[dict[str, Any]] = []
        for result in results:
            x_values = result.vectors[0].values
            y_values = result.vectors[1].values
            turbine = result.data_additional.get("turbine", result.short_description)
            metric = result.data_additional.get("metric", result.vectors[1].name.upper())
            for x_value, y_value in zip(x_values, y_values, strict=False):
                rows.append(
                    {
                        "x": datetime.fromtimestamp(x_value, tz=timezone.utc).isoformat(),
                        "y": y_value,
                        "series_name": result.short_description,
                        "turbine": turbine,
                        "metric": metric,
                    }
                )
        return pd.DataFrame(rows)
