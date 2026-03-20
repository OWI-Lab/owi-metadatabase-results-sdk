"""Pydantic models for the results extension."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnalysisKind(str, Enum):
    """Supported analysis categories."""

    HISTOGRAM = "histogram"
    TIME_SERIES = "time_series"
    COMPARISON = "comparison"


class ResultScope(str, Enum):
    """Supported result scopes."""

    SITE = "site"
    LOCATION = "location"


class AnalysisDefinition(BaseModel):
    """Validated analysis metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source_type: str
    source: str | None = None
    description: str | None = None
    user: str | None = None
    timestamp: datetime | None = None
    additional_data: dict[str, Any] = Field(default_factory=dict)


class ResultVector(BaseModel):
    """Validated numeric vector metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str
    unit: str
    values: list[float]

    @field_validator("values")
    @classmethod
    def validate_values(cls, values: list[float]) -> list[float]:
        """Require non-empty numeric vectors."""
        if not values:
            raise ValueError("Result vectors must contain at least one value.")
        return values


class RelatedObject(BaseModel):
    """Reference to an arbitrary Django object related to a result."""

    model_config = ConfigDict(extra="forbid")

    type: str
    id: int


class ResultSeries(BaseModel):
    """One logical result series compatible with a single Django row."""

    model_config = ConfigDict(extra="forbid")

    analysis_name: str
    analysis_kind: AnalysisKind
    result_scope: ResultScope
    short_description: str
    description: str | None = None
    site_id: int | None = None
    location_id: int | None = None
    related_object: RelatedObject | None = None
    data_additional: dict[str, Any] = Field(default_factory=dict)
    vectors: list[ResultVector] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def validate_scope_and_vectors(self) -> ResultSeries:
        """Validate vector alignment and scope requirements."""
        vector_lengths = {len(vector.values) for vector in self.vectors}
        if len(vector_lengths) != 1:
            raise ValueError("All result vectors must have identical lengths.")
        if self.result_scope == ResultScope.SITE and self.site_id is None:
            raise ValueError("Site scoped results require site_id.")
        if self.result_scope == ResultScope.LOCATION and self.location_id is None:
            raise ValueError("Location scoped results require location_id.")
        return self

    def to_record_payload(self, analysis_id: int) -> dict[str, Any]:
        """Serialize this series to the fixed Django schema."""
        payload: dict[str, Any] = {
            "analysis": analysis_id,
            "site": self.site_id,
            "location": self.location_id,
            "short_description": self.short_description,
            "description": self.description,
            "additional_data": {
                "analysis_kind": self.analysis_kind.value,
                "result_scope": self.result_scope.value,
                **self.data_additional,
            },
        }
        if self.related_object is not None:
            payload["related_object"] = self.related_object.model_dump()
        for index, vector in enumerate(self.vectors, start=1):
            payload[f"name_col{index}"] = vector.name
            payload[f"units_col{index}"] = vector.unit
            payload[f"value_col{index}"] = vector.values
        for index in range(len(self.vectors) + 1, 4):
            payload[f"name_col{index}"] = None
            payload[f"units_col{index}"] = None
            payload[f"value_col{index}"] = None
        return payload


class AnalysisRecordPayload(BaseModel):
    """Validated payload sent to the Django Analysis endpoint."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source_type: str
    source: str | None = None
    description: str | None = None
    user: str | None = None
    additional_data: dict[str, Any] = Field(default_factory=dict)


class ResultRecordPayload(BaseModel):
    """Validated payload sent to the Django Result endpoint."""

    model_config = ConfigDict(extra="forbid")

    analysis: int
    site: int | None = None
    location: int | None = None
    related_object: RelatedObject | None = None
    name_col1: str
    name_col2: str
    name_col3: str | None = None
    units_col1: str
    units_col2: str
    units_col3: str | None = None
    value_col1: list[float]
    value_col2: list[float]
    value_col3: list[float] | None = None
    short_description: str
    description: str | None = None
    additional_data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_lengths(self) -> ResultRecordPayload:
        """Require aligned persisted vectors."""
        lengths = {len(self.value_col1), len(self.value_col2)}
        if self.value_col3 is not None:
            lengths.add(len(self.value_col3))
        if len(lengths) != 1:
            raise ValueError("Persisted value columns must have identical lengths.")
        return self


class ResultQuery(BaseModel):
    """Validated high-level query filters."""

    model_config = ConfigDict(extra="forbid")

    analysis_name: str | None = None
    analysis_id: int | None = None
    site_id: int | None = None
    location_id: int | None = None
    turbine: str | None = None
    short_description: str | None = None
    timestamp_from: datetime | None = None
    timestamp_to: datetime | None = None
    backend_filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp_from", "timestamp_to")
    @classmethod
    def validate_timezone(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware datetimes."""
        if value is not None and value.tzinfo is None:
            raise ValueError("Datetime filters must be timezone-aware.")
        return value

    def to_backend_filters(self) -> dict[str, Any]:
        """Translate friendly query fields to backend filters."""
        filters = dict(self.backend_filters)
        if self.analysis_id is not None:
            filters["analysis"] = self.analysis_id
        if self.analysis_name is not None:
            filters["analysis__name"] = self.analysis_name
        if self.site_id is not None:
            filters["site"] = self.site_id
        if self.location_id is not None:
            filters["location"] = self.location_id
        if self.short_description is not None:
            filters["short_description"] = self.short_description
        if self.turbine is not None:
            filters["additional_data__turbine"] = self.turbine
        if self.timestamp_from is not None:
            filters["additional_data__timestamp_from"] = self.timestamp_from.isoformat()
        if self.timestamp_to is not None:
            filters["additional_data__timestamp_to"] = self.timestamp_to.isoformat()
        return filters


class PlotRequest(BaseModel):
    """Validated plot request."""

    model_config = ConfigDict(extra="forbid")

    analysis_name: str
    filters: ResultQuery = Field(default_factory=ResultQuery)
    title: str | None = None
    group_by: str | None = None
    plot_type: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class PlotResponse(BaseModel):
    """Structured chart response."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    chart: Any
    notebook: Any | None = None
    html: str
    json_options: str
