"""Tests for Django-compatible serializers."""

from __future__ import annotations

from owi.metadatabase.results.models import (
    AnalysisDefinition,
    AnalysisKind,
    RelatedObject,
    ResultScope,
    ResultSeries,
    ResultVector,
)
from owi.metadatabase.results.serializers import (
    DjangoAnalysisSerializer,
    DjangoResultSerializer,
    _optional_int,
    _optional_mapping,
    _optional_str,
)


class TestOptionalStr:
    def test_none_returns_none(self) -> None:
        assert _optional_str(None) is None

    def test_nan_returns_none(self) -> None:
        assert _optional_str(float("nan")) is None

    def test_string_passthrough(self) -> None:
        assert _optional_str("hello") == "hello"

    def test_int_coerced(self) -> None:
        assert _optional_str(42) == "42"


class TestOptionalInt:
    def test_none_returns_none(self) -> None:
        assert _optional_int(None) is None

    def test_nan_returns_none(self) -> None:
        assert _optional_int(float("nan")) is None

    def test_float_coerced(self) -> None:
        assert _optional_int(3.0) == 3

    def test_int_passthrough(self) -> None:
        assert _optional_int(7) == 7


class TestOptionalMapping:
    def test_none_returns_empty(self) -> None:
        assert _optional_mapping(None) == {}

    def test_nan_returns_empty(self) -> None:
        assert _optional_mapping(float("nan")) == {}

    def test_dict_passthrough(self) -> None:
        assert _optional_mapping({"a": 1}) == {"a": 1}

    def test_valid_json_string(self) -> None:
        assert _optional_mapping('{"key": "val"}') == {"key": "val"}

    def test_invalid_json_string(self) -> None:
        assert _optional_mapping("not json") == {}

    def test_json_array_string_returns_empty(self) -> None:
        assert _optional_mapping("[1, 2]") == {}

    def test_non_mapping_type_returns_empty(self) -> None:
        assert _optional_mapping(42) == {}


class TestDjangoAnalysisSerializer:
    def test_to_payload_and_from_mapping_roundtrip(self) -> None:
        definition = AnalysisDefinition(
            name="TestAnalysis",
            model_definition_id=9,
            location_id=None,
            source_type="script",
            source="test.py",
            description="A test analysis",
            user="user1",
            additional_data={"custom": "data"},
        )
        serializer = DjangoAnalysisSerializer()
        payload = serializer.to_payload(definition)
        assert payload["name"] == "TestAnalysis"
        assert payload["model_definition_id"] == 9
        assert "location_id" not in payload
        assert payload["source_type"] == "script"
        assert payload["additional_data"]["custom"] == "data"

    def test_from_mapping_handles_data_additional_key(self) -> None:
        serializer = DjangoAnalysisSerializer()
        result = serializer.from_mapping(
            {
                "name": "Test",
                "model_definition_id": 9,
                "location_id": None,
                "source_type": "script",
                "data_additional": '{"custom": "value"}',
            }
        )
        assert result.additional_data == {"custom": "value"}

    def test_to_payload_excludes_none_fields(self) -> None:
        definition = AnalysisDefinition(name="Test", model_definition_id=9, location_id=None, source_type="script")
        serializer = DjangoAnalysisSerializer()
        payload = serializer.to_payload(definition)
        assert "source" not in payload
        assert "description" not in payload
        assert "user" not in payload
        assert "location_id" not in payload
        assert payload["model_definition_id"] == 9


class TestDjangoResultSerializer:
    def test_to_payload_two_vectors(self) -> None:
        series = ResultSeries(
            analysis_name="Test",
            analysis_kind=AnalysisKind.HISTOGRAM,
            result_scope=ResultScope.SITE,
            short_description="test",
            site_id=1,
            vectors=[
                ResultVector(name="x", unit="m/s", values=[1.0, 2.0]),
                ResultVector(name="y", unit="count", values=[10.0, 20.0]),
            ],
        )
        serializer = DjangoResultSerializer()
        payload = serializer.to_payload(series, analysis_id=5)
        assert payload["analysis"] == 5
        assert payload["name_col1"] == "x"
        assert payload["name_col2"] == "y"
        assert "value_col3" not in payload  # exclude_none=True drops missing vectors

    def test_to_payload_three_vectors(self) -> None:
        series = ResultSeries(
            analysis_name="Test",
            analysis_kind=AnalysisKind.HISTOGRAM,
            result_scope=ResultScope.SITE,
            short_description="test",
            site_id=1,
            vectors=[
                ResultVector(name="a", unit="u1", values=[1.0]),
                ResultVector(name="b", unit="u2", values=[2.0]),
                ResultVector(name="c", unit="u3", values=[3.0]),
            ],
        )
        serializer = DjangoResultSerializer()
        payload = serializer.to_payload(series, analysis_id=7)
        assert payload["name_col3"] == "c"
        assert payload["value_col3"] == [3.0]

    def test_from_mapping_with_related_object(self) -> None:
        serializer = DjangoResultSerializer()
        result = serializer.from_mapping(
            {
                "analysis": 1,
                "site": 1,
                "location": None,
                "name_col1": "x",
                "units_col1": "m/s",
                "value_col1": [1.0],
                "name_col2": "y",
                "units_col2": "count",
                "value_col2": [10.0],
                "short_description": "test",
                "related_object": {"type": "turbine", "id": 42},
                "data_additional": {"analysis_kind": "histogram", "result_scope": "site"},
            }
        )
        assert result.related_object is not None
        assert result.related_object.type == "turbine"
        assert result.related_object.id == 42

    def test_from_mapping_no_related_object(self) -> None:
        serializer = DjangoResultSerializer()
        result = serializer.from_mapping(
            {
                "analysis": 1,
                "site": 1,
                "location": None,
                "name_col1": "x",
                "units_col1": "m/s",
                "value_col1": [1.0],
                "name_col2": "y",
                "units_col2": "count",
                "value_col2": [10.0],
                "short_description": "test",
                "data_additional": {"analysis_kind": "histogram", "result_scope": "site"},
            }
        )
        assert result.related_object is None

    def test_to_payload_includes_related_object(self) -> None:
        series = ResultSeries(
            analysis_name="Test",
            analysis_kind=AnalysisKind.HISTOGRAM,
            result_scope=ResultScope.SITE,
            short_description="test",
            site_id=1,
            related_object=RelatedObject(type="turbine", id=42),
            vectors=[
                ResultVector(name="x", unit="m/s", values=[1.0]),
                ResultVector(name="y", unit="count", values=[2.0]),
            ],
        )
        serializer = DjangoResultSerializer()
        payload = serializer.to_payload(series, analysis_id=5)
        assert payload["related_object"] == {"type": "turbine", "id": 42}

    def test_from_mapping_defaults_analysis_name_to_unknown(self) -> None:
        serializer = DjangoResultSerializer()
        result = serializer.from_mapping(
            {
                "analysis": 1,
                "site": 1,
                "name_col1": "x",
                "units_col1": "m/s",
                "value_col1": [1.0],
                "name_col2": "y",
                "units_col2": "count",
                "value_col2": [10.0],
                "short_description": "test",
                "data_additional": {"analysis_kind": "histogram", "result_scope": "site"},
            }
        )
        assert result.analysis_name == "unknown"
