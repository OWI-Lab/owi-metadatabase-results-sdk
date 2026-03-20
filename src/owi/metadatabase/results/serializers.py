"""Serializers for Django-compatible result payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pandas as pd

from .models import (
    AnalysisDefinition,
    AnalysisKind,
    AnalysisRecordPayload,
    RelatedObject,
    ResultRecordPayload,
    ResultScope,
    ResultSeries,
)


def _optional_str(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return int(value)


def _optional_mapping(value: Any) -> dict[str, Any]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, Mapping):
            return dict(decoded)
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {}


class DjangoAnalysisSerializer:
    """Convert between analysis metadata and Django payloads."""

    def to_payload(self, obj: AnalysisDefinition) -> dict[str, Any]:
        """Serialize a validated analysis definition."""
        payload = AnalysisRecordPayload(
            name=obj.name,
            source_type=obj.source_type,
            source=obj.source,
            description=obj.description,
            user=obj.user,
            additional_data=obj.additional_data,
        )
        return payload.model_dump(exclude_none=True)

    def from_mapping(self, mapping: Mapping[str, Any]) -> AnalysisDefinition:
        """Deserialize an analysis mapping."""
        additional_data = _optional_mapping(mapping.get("additional_data") or mapping.get("data_additional"))
        return AnalysisDefinition(
            name=str(mapping["name"]),
            source_type=str(mapping["source_type"]),
            source=_optional_str(mapping.get("source")),
            description=_optional_str(mapping.get("description")),
            user=_optional_str(mapping.get("user")),
            timestamp=mapping.get("timestamp"),
            additional_data=additional_data,
        )


class DjangoResultSerializer:
    """Convert between validated result series and Django payloads."""

    def to_payload(self, obj: ResultSeries, analysis_id: int) -> dict[str, Any]:
        """Serialize a validated result series."""
        payload = ResultRecordPayload(**obj.to_record_payload(analysis_id))
        return payload.model_dump(exclude_none=True)

    def from_mapping(self, mapping: Mapping[str, Any]) -> ResultSeries:
        """Deserialize a backend result row."""
        vectors: list[dict[str, Any]] = [
            {
                "name": str(mapping["name_col1"]),
                "unit": str(mapping["units_col1"]),
                "values": [float(value) for value in mapping["value_col1"]],
            },
            {
                "name": str(mapping["name_col2"]),
                "unit": str(mapping["units_col2"]),
                "values": [float(value) for value in mapping["value_col2"]],
            },
        ]
        value_col3 = mapping.get("value_col3")
        if value_col3 not in (None, []):
            vectors.append(
                {
                    "name": str(mapping["name_col3"]),
                    "unit": str(mapping["units_col3"]),
                    "values": [float(value) for value in value_col3],
                }
            )
        data_additional = _optional_mapping(mapping.get("additional_data") or mapping.get("data_additional"))
        return ResultSeries(
            analysis_name=str(data_additional.get("analysis_name", mapping.get("analysis_name", "unknown"))),
            analysis_kind=AnalysisKind(data_additional.get("analysis_kind", "comparison")),
            result_scope=ResultScope(data_additional.get("result_scope", "site")),
            short_description=str(mapping["short_description"]),
            description=_optional_str(mapping.get("description")),
            site_id=_optional_int(mapping.get("site")),
            location_id=_optional_int(mapping.get("location")),
            related_object=(
                RelatedObject.model_validate(mapping["related_object"])
                if mapping.get("related_object") is not None
                else None
            ),
            data_additional=data_additional,
            vectors=vectors,
        )
