"""Tests for validated results models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from owi.metadatabase.results.models import (
    AnalysisDefinition,
    AnalysisKind,
    PlotRequest,
    RelatedObject,
    ResultQuery,
    ResultRecordPayload,
    ResultScope,
    ResultSeries,
    ResultVector,
)


class TestAnalysisKind:
    def test_enum_values(self) -> None:
        assert AnalysisKind.HISTOGRAM.value == "histogram"
        assert AnalysisKind.TIME_SERIES.value == "time_series"
        assert AnalysisKind.COMPARISON.value == "comparison"

    def test_invalid_kind_raises(self) -> None:
        with pytest.raises(ValueError):
            AnalysisKind("unknown_kind")


class TestResultScope:
    def test_enum_values(self) -> None:
        assert ResultScope.SITE.value == "site"
        assert ResultScope.LOCATION.value == "location"

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValueError):
            ResultScope("unknown_scope")


class TestResultVector:
    def test_empty_values_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            ResultVector(name="x", unit="m/s", values=[])

    def test_valid_construction(self) -> None:
        vector = ResultVector(name="x", unit="m/s", values=[1.0, 2.0])
        assert vector.name == "x"
        assert len(vector.values) == 2

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ResultVector.model_validate({"name": "x", "unit": "m/s", "values": [1.0], "extra": "nope"})


class TestRelatedObject:
    def test_valid_construction(self) -> None:
        obj = RelatedObject(type="turbine", id=42)
        assert obj.type == "turbine"
        assert obj.id == 42

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            RelatedObject.model_validate({"type": "turbine", "id": 42, "extra": "nope"})


class TestResultSeries:
    def test_requires_aligned_vectors(self) -> None:
        with pytest.raises(ValueError, match="identical lengths"):
            ResultSeries(
                analysis_name="WindSpeedHistogram",
                analysis_kind=AnalysisKind.HISTOGRAM,
                result_scope=ResultScope.SITE,
                short_description="Series",
                site_id=1,
                vectors=[
                    ResultVector(name="x", unit="m/s", values=[0.0, 1.0]),
                    ResultVector(name="y", unit="count", values=[1.0]),
                ],
            )

    def test_site_scope_requires_site_id(self) -> None:
        with pytest.raises(ValueError, match="site_id"):
            ResultSeries(
                analysis_name="Test",
                analysis_kind=AnalysisKind.HISTOGRAM,
                result_scope=ResultScope.SITE,
                short_description="test",
                vectors=[
                    ResultVector(name="x", unit="u", values=[1.0]),
                    ResultVector(name="y", unit="u", values=[2.0]),
                ],
            )

    def test_location_scope_requires_location_id(self) -> None:
        with pytest.raises(ValueError, match="location_id"):
            ResultSeries(
                analysis_name="Test",
                analysis_kind=AnalysisKind.COMPARISON,
                result_scope=ResultScope.LOCATION,
                short_description="test",
                site_id=1,
                vectors=[
                    ResultVector(name="x", unit="u", values=[1.0]),
                    ResultVector(name="y", unit="u", values=[2.0]),
                ],
            )

    def test_min_two_vectors_required(self) -> None:
        with pytest.raises(ValidationError):
            ResultSeries(
                analysis_name="Test",
                analysis_kind=AnalysisKind.HISTOGRAM,
                result_scope=ResultScope.SITE,
                short_description="test",
                site_id=1,
                vectors=[ResultVector(name="x", unit="u", values=[1.0])],
            )

    def test_max_three_vectors(self) -> None:
        with pytest.raises(ValidationError):
            ResultSeries(
                analysis_name="Test",
                analysis_kind=AnalysisKind.HISTOGRAM,
                result_scope=ResultScope.SITE,
                short_description="test",
                site_id=1,
                vectors=[
                    ResultVector(name="a", unit="u", values=[1.0]),
                    ResultVector(name="b", unit="u", values=[1.0]),
                    ResultVector(name="c", unit="u", values=[1.0]),
                    ResultVector(name="d", unit="u", values=[1.0]),
                ],
            )

    def test_to_record_payload_two_vectors(self) -> None:
        series = ResultSeries(
            analysis_name="Test",
            analysis_kind=AnalysisKind.HISTOGRAM,
            result_scope=ResultScope.SITE,
            short_description="test",
            site_id=1,
            vectors=[
                ResultVector(name="x", unit="m/s", values=[1.0]),
                ResultVector(name="y", unit="count", values=[2.0]),
            ],
        )
        payload = series.to_record_payload(analysis_id=10)
        assert payload["analysis"] == 10
        assert payload["name_col1"] == "x"
        assert payload["name_col2"] == "y"
        assert payload["name_col3"] is None
        assert payload["value_col3"] is None

    def test_to_record_payload_three_vectors(self) -> None:
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
        payload = series.to_record_payload(analysis_id=5)
        assert payload["name_col3"] == "c"
        assert payload["value_col3"] == [3.0]

    def test_to_record_payload_includes_additional_data(self) -> None:
        series = ResultSeries(
            analysis_name="Test",
            analysis_kind=AnalysisKind.HISTOGRAM,
            result_scope=ResultScope.SITE,
            short_description="test",
            site_id=1,
            data_additional={"custom": "value"},
            vectors=[
                ResultVector(name="x", unit="u", values=[1.0]),
                ResultVector(name="y", unit="u", values=[2.0]),
            ],
        )
        payload = series.to_record_payload(analysis_id=1)
        assert payload["additional_data"]["custom"] == "value"
        assert payload["additional_data"]["analysis_kind"] == "histogram"


class TestAnalysisDefinition:
    def test_defaults(self) -> None:
        defn = AnalysisDefinition(name="Test", model_definition_id=7, location_id=None, source_type="script")
        assert defn.source is None
        assert defn.additional_data == {}
        assert defn.location_id is None

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisDefinition.model_validate(
                {
                    "name": "Test",
                    "model_definition_id": 7,
                    "location_id": None,
                    "source_type": "script",
                    "extra": "no",
                }
            )


class TestResultRecordPayload:
    def test_misaligned_vectors_rejected(self) -> None:
        with pytest.raises(ValidationError, match="identical lengths"):
            ResultRecordPayload(
                analysis=1,
                name_col1="x",
                units_col1="u",
                value_col1=[1.0, 2.0],
                name_col2="y",
                units_col2="u",
                value_col2=[1.0],
                short_description="test",
            )

    def test_three_vector_misalignment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="identical lengths"):
            ResultRecordPayload(
                analysis=1,
                name_col1="x",
                units_col1="u",
                value_col1=[1.0],
                name_col2="y",
                units_col2="u",
                value_col2=[1.0],
                name_col3="z",
                units_col3="u",
                value_col3=[1.0, 2.0],
                short_description="test",
            )


class TestResultQuery:
    def test_requires_timezone_aware_datetimes(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ResultQuery(timestamp_from=datetime(2024, 1, 1))

    def test_timestamp_to_also_validates(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ResultQuery(timestamp_to=datetime(2024, 12, 31))

    def test_to_backend_filters(self) -> None:
        query = ResultQuery(
            analysis_name="LifetimeDesignVerification",
            site_id=10,
            timestamp_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        filters = query.to_backend_filters()
        assert filters["analysis__name"] == "LifetimeDesignVerification"
        assert filters["site"] == 10
        assert filters["additional_data__timestamp_from"].startswith("2024-01-01")

    def test_to_backend_filters_includes_turbine(self) -> None:
        query = ResultQuery(turbine="WFA03")
        filters = query.to_backend_filters()
        assert filters["additional_data__turbine"] == "WFA03"

    def test_to_backend_filters_includes_location_id(self) -> None:
        query = ResultQuery(location_id=5)
        filters = query.to_backend_filters()
        assert filters["location"] == 5

    def test_to_backend_filters_includes_short_description(self) -> None:
        query = ResultQuery(short_description="test")
        filters = query.to_backend_filters()
        assert filters["short_description"] == "test"

    def test_to_backend_filters_merges_backend_filters(self) -> None:
        query = ResultQuery(analysis_id=1, backend_filters={"custom": "value"})
        filters = query.to_backend_filters()
        assert filters["analysis__id"] == 1
        assert filters["custom"] == "value"

    def test_to_backend_filters_prefers_analysis_id_over_name(self) -> None:
        query = ResultQuery(analysis_id=1, analysis_name="LifetimeDesignFrequencies")
        filters = query.to_backend_filters()
        assert filters["analysis__id"] == 1
        assert "analysis__name" not in filters

    def test_empty_query_produces_empty_filters(self) -> None:
        filters = ResultQuery().to_backend_filters()
        assert filters == {}


class TestPlotRequest:
    def test_default_construction(self) -> None:
        req = PlotRequest(analysis_name="Test")
        assert req.filters.analysis_name is None
        assert req.context == {}

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            PlotRequest.model_validate({"analysis_name": "Test", "extra": "no"})
