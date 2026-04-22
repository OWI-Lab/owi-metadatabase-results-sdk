"""Tests for high-level services and analyses."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from owi.metadatabase.results import LifetimeDesignFrequencies, WindSpeedHistogram
from owi.metadatabase.results.analyses.lifetime_design_verification import LifetimeDesignVerification
from owi.metadatabase.results.models import ResultQuery
from owi.metadatabase.results.serializers import DjangoResultSerializer
from owi.metadatabase.results.services import ResultsService
from owi.metadatabase.results.services import get_results as module_get_results
from owi.metadatabase.results.services import plot_results as module_plot_results


class StubRepository:
    """Small repository stub for service tests."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def list_analyses(self, name: str | None = None, **kwargs: Any) -> pd.DataFrame:
        return pd.DataFrame()

    def list_results(self, query: Any) -> pd.DataFrame:
        return self.frame

    def create_analysis(self, payload: Any) -> Any:
        return payload

    def create_result(self, payload: Any) -> dict[str, Any]:
        return {"item": payload}

    def create_results_bulk(self, payloads: Any) -> dict[str, Any]:
        return {"items": list(payloads)}

    def create_or_update_results_bulk(self, payloads: Any) -> dict[str, Any]:
        return {"items": list(payloads)}

    def update_result(self, result_id: int, payload: Any) -> dict[str, Any]:
        return {"id": result_id, "item": payload}

    def get_location_frame(self, location_ids: Any) -> pd.DataFrame:
        return pd.DataFrame()


class StubLocationRepository(StubRepository):
    """Repository stub that also exposes location metadata for geo plots."""

    def __init__(self, frame: pd.DataFrame, location_frame: pd.DataFrame) -> None:
        super().__init__(frame)
        self.location_frame = location_frame

    def get_location_frame(self, location_ids: Any) -> pd.DataFrame:
        result = self.location_frame[self.location_frame["id"].isin(location_ids)].copy()
        return pd.DataFrame(result)


class MultiAnalysisRepository(StubRepository):
    """Repository stub that returns different result frames per analysis name."""

    def __init__(self, frames_by_analysis: dict[str, pd.DataFrame]) -> None:
        super().__init__(pd.DataFrame())
        self.frames_by_analysis = frames_by_analysis
        self.queries: list[Any] = []

    def list_results(self, query: Any) -> pd.DataFrame:
        self.queries.append(query)
        return self.frames_by_analysis.get(query.analysis_name, pd.DataFrame())


def test_wind_speed_histogram_to_results_and_plot() -> None:
    analysis = WindSpeedHistogram()
    results = analysis.to_results(
        {
            "series": [
                {
                    "title": "Design",
                    "scope_label": "Site",
                    "site_id": 1,
                    "bins": [(0.0, 1.0), (1.0, 2.0)],
                    "values": [1.0, 2.0],
                }
            ]
        }
    )
    response = analysis.plot(results)
    options = json.loads(response.json_options)
    assert len(results) == 1
    assert "Design" in response.html
    assert response.notebook is not None
    assert "series" in response.json_options
    assert options["textStyle"]["fontFamily"] == "monospace"
    assert options["title"][0]["top"] != options["legend"][0]["top"]


def test_lifetime_design_verification_to_results() -> None:
    analysis = LifetimeDesignVerification()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    "turbine": "WFA03",
                    "FA1": 0.356,
                    "SS1": 0.357,
                    "location_id": 5,
                },
                {
                    "timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
                    "turbine": "WFA03",
                    "FA1": 0.355,
                    "SS1": 0.356,
                    "location_id": 5,
                },
            ]
        }
    )
    assert len(results) == 2
    assert results[0].location_id == 5


def test_results_service_get_results() -> None:
    analysis = WindSpeedHistogram()
    series = analysis.to_results(
        {
            "series": [
                {
                    "title": "Design",
                    "scope_label": "Site",
                    "site_id": 1,
                    "bins": [(0.0, 1.0), (1.0, 2.0)],
                    "values": [1.0, 2.0],
                }
            ]
        }
    )[0]
    payload = series.to_record_payload(analysis_id=11)
    frame = pd.DataFrame([payload])
    service = ResultsService(repository=StubRepository(frame))
    result = service.get_results("WindSpeedHistogram")
    assert list(result.columns) == ["series_name", "scope", "bin_left", "bin_right", "value"]
    assert len(result) == 2


def test_results_service_deserialize_result_series_from_dataframe() -> None:
    serializer = DjangoResultSerializer()
    frame = pd.DataFrame(
        [
            {
                "analysis": 99,
                "site": None,
                "location": 9,
                "name_col1": "reference_index",
                "units_col1": "index",
                "value_col1": [0.0, 1.0],
                "name_col2": "fa1",
                "units_col2": "Hz",
                "value_col2": [0.3406, 0.3330],
                "name_col3": None,
                "units_col3": None,
                "value_col3": [],
                "short_description": "WFA03 - FA1",
                "description": None,
                "data_additional": {
                    "analysis_kind": "comparison",
                    "result_scope": "location",
                    "reference_labels": ["INFL", "ACTU"],
                },
            }
        ]
    )
    service = ResultsService(repository=StubRepository(frame))

    result = service.deserialize_result_series(frame)

    assert len(result) == 1
    assert result[0] == serializer.from_mapping(frame.to_dict(orient="records")[0])  # ty: ignore[invalid-argument-type]
    assert len(result[0].vectors) == 2


def test_results_service_get_result_series_fetches_typed_results() -> None:
    analysis = LifetimeDesignFrequencies()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "turbine": "WFA03",
                    "reference": "INFL",
                    "FA1": 0.3406,
                    "SS1": 0.3407,
                    "location_id": 9,
                },
                {
                    "turbine": "WFA03",
                    "reference": "ACTU",
                    "FA1": 0.3330,
                    "SS1": 0.3332,
                    "location_id": 9,
                },
            ]
        }
    )
    frame = pd.DataFrame([series.to_record_payload(analysis_id=17) for series in results])
    service = ResultsService(repository=StubRepository(frame))

    retrieved = service.get_result_series("LifetimeDesignFrequencies", filters={"analysis_id": 17})

    assert len(retrieved) == 2
    assert all(series.short_description.startswith("WFA03") for series in retrieved)


def test_results_service_get_location_frame_filters_requested_ids() -> None:
    service = ResultsService(
        repository=StubLocationRepository(
            pd.DataFrame(),
            pd.DataFrame(
                [
                    {"id": 9, "title": "WFA03", "northing": 51.5, "easting": 2.8},
                    {"id": 10, "title": "WFB07", "northing": 51.6, "easting": 2.9},
                ]
            ),
        )
    )

    location_frame = service.get_location_frame([10])

    assert list(location_frame["id"]) == [10]
    assert list(location_frame.columns) == ["id", "title", "northing", "easting"]


def test_results_service_get_location_frame_empty_ids_returns_empty_schema() -> None:
    service = ResultsService(repository=StubRepository(pd.DataFrame()))

    location_frame = service.get_location_frame([])

    assert location_frame.empty
    assert list(location_frame.columns) == ["id", "title", "northing", "easting"]


def test_lifetime_design_frequencies_to_results() -> None:
    analysis = LifetimeDesignFrequencies()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "turbine": "WFA03",
                    "reference": "INFL",
                    "FA1": 0.3406,
                    "SS1": 0.3407,
                    "location_id": 9,
                },
                {
                    "turbine": "WFA03",
                    "reference": "ACTU",
                    "FA1": 0.3330,
                    "SS1": 0.3332,
                    "location_id": 9,
                },
            ]
        }
    )
    assert len(results) == 2
    reconstructed = analysis.from_results(results)
    assert set(reconstructed["reference"]) == {"INFL", "ACTU"}
    payload = results[0].to_record_payload(analysis_id=17)
    assert payload["additional_data"] == {
        "analysis_kind": "comparison",
        "result_scope": "location",
        "reference_labels": ["INFL", "ACTU"],
    }


def test_lifetime_design_frequencies_plot_uses_reference_legend() -> None:
    analysis = LifetimeDesignFrequencies()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "turbine": "WFA03",
                    "reference": "INFL",
                    "FA1": 0.3406,
                    "SS1": 0.3407,
                    "location_id": 9,
                },
                {
                    "turbine": "WFA03",
                    "reference": "ACTU",
                    "FA1": 0.3330,
                    "SS1": 0.3332,
                    "location_id": 9,
                },
            ]
        }
    )

    response = analysis.plot(results)
    options = json.loads(response.json_options)

    assert set(options) == {"FA1", "SS1"}
    assert [series["name"] for series in options["FA1"]["series"]] == ["ACTU", "INFL"]
    assert "INFL" in response.html
    assert "ACTU" in response.html


def test_results_service_plot_results_supports_geo_plot_type() -> None:
    analysis = LifetimeDesignFrequencies()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "turbine": "WFA03",
                    "reference": "INFL",
                    "FA1": 0.3406,
                    "SS1": 0.3407,
                    "location_id": 9,
                },
                {
                    "turbine": "WFA03",
                    "reference": "ACTU",
                    "FA1": 0.3330,
                    "SS1": 0.3332,
                    "location_id": 9,
                },
            ]
        }
    )
    frame = pd.DataFrame([series.to_record_payload(analysis_id=17) for series in results])
    location_frame = pd.DataFrame(
        [
            {"id": 9, "title": "WFA03", "northing": 51.5, "easting": 2.8},
        ]
    )
    service = ResultsService(repository=StubLocationRepository(frame, location_frame))

    response = service.plot_results("LifetimeDesignFrequencies", plot_type="geo")
    options = json.loads(response.json_options)

    assert "Metric" in response.html
    assert "Reference" in response.html
    assert options["FA1"]["INFL"]["legend"][0]["show"] is False


def test_results_service_plot_results_supports_assembled_plot_type() -> None:
    frequency_analysis = LifetimeDesignFrequencies()
    verification_analysis = LifetimeDesignVerification()
    frequency_results = frequency_analysis.to_results(
        {
            "rows": [
                {
                    "turbine": "WFA03",
                    "reference": "INFL",
                    "FA1": 2.4123,
                    "location_id": 9,
                },
                {
                    "turbine": "WFA03",
                    "reference": "ACTU",
                    "FA1": 1.9184,
                    "location_id": 9,
                },
                {
                    "turbine": "WFB07",
                    "reference": "INFL",
                    "FA1": 2.1038,
                    "location_id": 10,
                },
                {
                    "turbine": "WFB07",
                    "reference": "ACTU",
                    "FA1": 1.4472,
                    "location_id": 10,
                },
            ]
        }
    )
    verification_results = verification_analysis.to_results(
        {
            "rows": [
                {
                    "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    "turbine": "WFA03",
                    "FA1": 2.5517,
                    "location_id": 9,
                },
                {
                    "timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
                    "turbine": "WFB07",
                    "FA1": 2.2746,
                    "location_id": 10,
                },
            ]
        }
    )
    repository = MultiAnalysisRepository(
        {
            "LifetimeDesignFrequencies": pd.DataFrame(
                [series.to_record_payload(analysis_id=17) for series in frequency_results]
            ),
            "LifetimeDesignVerification": pd.DataFrame(
                [series.to_record_payload(analysis_id=19) for series in verification_results]
            ),
        }
    )
    service = ResultsService(repository=repository)

    response = service.plot_results(
        "LifetimeDesignVerification",
        filters={"analysis_id": 999},
        plot_type="assembled",
    )
    options = json.loads(response.json_options)

    assert "FA1" in options
    assert options["FA1"]["xAxis"][0]["data"] == ["WFA03", "WFB07"]
    assert options["FA1"]["legend"][0]["data"] == ["INFL", "ACTU"]
    assert [series["name"] for series in options["FA1"]["series"]] == ["INFL", "ACTU", "Verification"]
    assert [query.analysis_name for query in repository.queries] == [
        "LifetimeDesignFrequencies",
        "LifetimeDesignVerification",
    ]
    assert repository.queries[0].analysis_id is None
    assert repository.queries[1].analysis_id == 999


def test_results_service_plot_results_supports_assembled_plot_from_frequency_owner() -> None:
    frequency_analysis = LifetimeDesignFrequencies()
    verification_analysis = LifetimeDesignVerification()
    repository = MultiAnalysisRepository(
        {
            "LifetimeDesignFrequencies": pd.DataFrame(
                [
                    series.to_record_payload(analysis_id=17)
                    for series in frequency_analysis.to_results(
                        {
                            "rows": [
                                {
                                    "turbine": "WFA03",
                                    "reference": "INFL",
                                    "FA1": 2.4123,
                                    "location_id": 9,
                                },
                                {
                                    "turbine": "WFA03",
                                    "reference": "ACTU",
                                    "FA1": 1.9184,
                                    "location_id": 9,
                                },
                            ]
                        }
                    )
                ]
            ),
            "LifetimeDesignVerification": pd.DataFrame(
                [
                    series.to_record_payload(analysis_id=19)
                    for series in verification_analysis.to_results(
                        {
                            "rows": [
                                {
                                    "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                                    "turbine": "WFA03",
                                    "FA1": 2.5517,
                                    "location_id": 9,
                                }
                            ]
                        }
                    )
                ]
            ),
        }
    )
    service = ResultsService(repository=repository)

    response = service.plot_results("LifetimeDesignFrequencies", plot_type="assembled")
    options = json.loads(response.json_options)

    assert "FA1" in options
    assert options["FA1"]["legend"][0]["data"] == ["INFL", "ACTU"]


def test_results_service_comparison_and_location_plots_are_distinct() -> None:
    analysis = LifetimeDesignFrequencies()
    results = analysis.to_results(
        {
            "rows": [
                {
                    "turbine": "WFA03",
                    "reference": "INFL",
                    "FA1": 0.3406,
                    "SS1": 0.3407,
                    "location_id": 9,
                },
                {
                    "turbine": "WFA03",
                    "reference": "ACTU",
                    "FA1": 0.3330,
                    "SS1": 0.3332,
                    "location_id": 9,
                },
                {
                    "turbine": "WFB07",
                    "reference": "INFL",
                    "FA1": 0.3201,
                    "SS1": 0.3204,
                    "location_id": 10,
                },
                {
                    "turbine": "WFB07",
                    "reference": "ACTU",
                    "FA1": 0.3111,
                    "SS1": 0.3114,
                    "location_id": 10,
                },
            ]
        }
    )
    frame = pd.DataFrame([series.to_record_payload(analysis_id=17) for series in results])
    location_frame = pd.DataFrame(
        [
            {"id": 9, "title": "WFA03", "northing": 51.5, "easting": 2.8},
            {"id": 10, "title": "WFB07", "northing": 51.6, "easting": 2.9},
        ]
    )
    service = ResultsService(repository=StubLocationRepository(frame, location_frame))

    comparison_response = service.plot_results("LifetimeDesignFrequencies", plot_type="comparison")
    location_response = service.plot_results("LifetimeDesignFrequencies", plot_type="location")
    comparison_options = json.loads(comparison_response.json_options)
    location_options = json.loads(location_response.json_options)

    assert comparison_options["FA1"]["xAxis"][0]["data"] == ["INFL", "ACTU"]
    assert location_options["FA1"]["xAxis"][0]["data"] == ["WFA03", "WFB07"]
    assert [series["name"] for series in comparison_options["FA1"]["series"]] == ["WFA03", "WFB07"]
    assert [series["name"] for series in location_options["FA1"]["series"]] == ["ACTU", "INFL"]


def test_django_result_serializer_ignores_empty_third_vector() -> None:
    serializer = DjangoResultSerializer()
    result = serializer.from_mapping(
        {
            "analysis": 99,
            "site": None,
            "location": 9,
            "name_col1": "reference_index",
            "units_col1": "index",
            "value_col1": [0.0, 1.0],
            "name_col2": "fa1",
            "units_col2": "Hz",
            "value_col2": [0.3406, 0.3330],
            "name_col3": None,
            "units_col3": None,
            "value_col3": [],
            "short_description": "WFA03 - FA1",
            "description": None,
            "data_additional": {
                "analysis_kind": "comparison",
                "result_scope": "location",
                "reference_labels": ["INFL", "ACTU"],
            },
        }
    )
    assert len(result.vectors) == 2


def test_django_result_serializer_reads_json_data_additional() -> None:
    serializer = DjangoResultSerializer()
    result = serializer.from_mapping(
        {
            "analysis": 99,
            "site": None,
            "location": 9,
            "name_col1": "reference_index",
            "units_col1": "index",
            "value_col1": [0.0, 1.0],
            "name_col2": "fa1",
            "units_col2": "Hz",
            "value_col2": [0.3406, 0.3330],
            "name_col3": None,
            "units_col3": None,
            "value_col3": None,
            "short_description": "WFA03 - FA1",
            "description": None,
            "data_additional": json.dumps(
                {
                    "analysis_kind": "comparison",
                    "result_scope": "location",
                    "reference_labels": ["INFL", "ACTU"],
                }
            ),
        }
    )

    reconstructed = LifetimeDesignFrequencies().from_results([result])
    assert list(reconstructed["reference"]) == ["INFL", "ACTU"]


class TestCoerceQuery:
    """Tests for ResultsService._coerce_query."""

    def test_dict_filters_become_query(self) -> None:
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        query = service._coerce_query("WindSpeedHistogram", {"analysis_id": 5})
        assert isinstance(query, ResultQuery)
        assert query.analysis_name == "WindSpeedHistogram"
        assert query.analysis_id == 5

    def test_none_filters_become_default_query(self) -> None:
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        query = service._coerce_query("WindSpeedHistogram")
        assert query.analysis_name == "WindSpeedHistogram"

    def test_query_object_passthrough(self) -> None:
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        original = ResultQuery(analysis_name="WindSpeedHistogram", analysis_id=7)
        query = service._coerce_query("WindSpeedHistogram", original)
        assert query is original

    def test_query_without_name_gets_filled(self) -> None:
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        original = ResultQuery(analysis_id=7)
        query = service._coerce_query("WindSpeedHistogram", original)
        assert query.analysis_name == "WindSpeedHistogram"
        assert query is not original  # model_copy creates a new object


class TestDeserializeResultSeriesFromList:
    def test_list_of_dicts(self) -> None:
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        records = [
            {
                "analysis": 99,
                "site": 1,
                "location": None,
                "name_col1": "bin_left",
                "units_col1": "m/s",
                "value_col1": [0.0],
                "name_col2": "value",
                "units_col2": "-",
                "value_col2": [1.0],
                "name_col3": "bin_right",
                "units_col3": "m/s",
                "value_col3": [1.0],
                "short_description": "Design",
                "description": None,
                "data_additional": {"analysis_kind": "histogram", "result_scope": "site"},
            }
        ]
        result = service.deserialize_result_series(records)
        assert len(result) == 1
        assert result[0].short_description == "Design"


class TestGetLocationFrameEdgeCases:
    def test_repository_without_get_location_frame_returns_empty(self) -> None:
        """Repository with no get_location_frame attribute returns empty schema."""
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        frame = service.get_location_frame([9])
        assert frame.empty
        assert list(frame.columns) == ["id", "title", "northing", "easting"]

    def test_get_location_frame_returns_non_dataframe(self) -> None:
        """If get_location_frame returns non-DataFrame, service returns empty schema."""

        class BadLocationRepo(StubRepository):
            def get_location_frame(self, location_ids: list[int]) -> str:  # ty: ignore[invalid-method-override]
                return "not a frame"

        service = ResultsService(repository=BadLocationRepo(pd.DataFrame()))  # ty: ignore[invalid-argument-type]
        frame = service.get_location_frame([9])
        assert frame.empty

    def test_get_location_frame_returns_empty_frame(self) -> None:
        service = ResultsService(
            repository=StubLocationRepository(
                pd.DataFrame(),
                pd.DataFrame(columns=["id", "title", "northing", "easting"]),
            )
        )
        frame = service.get_location_frame([999])
        assert frame.empty


class TestPlotContext:
    def test_non_geo_returns_empty(self) -> None:
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        ctx = service._plot_context([], plot_type="comparison")
        assert ctx == {}

    def test_none_plot_type_returns_empty(self) -> None:
        service = ResultsService(repository=StubRepository(pd.DataFrame()))
        ctx = service._plot_context([], plot_type=None)
        assert ctx == {}

    def test_geo_adds_location_frame(self) -> None:
        from owi.metadatabase.results.models import AnalysisKind, ResultScope, ResultSeries, ResultVector

        record = ResultSeries(
            analysis_name="test",
            analysis_kind=AnalysisKind.COMPARISON,
            result_scope=ResultScope.LOCATION,
            short_description="...",
            location_id=9,
            vectors=[
                ResultVector(name="x", unit="u", values=[1.0]),
                ResultVector(name="y", unit="v", values=[2.0]),
            ],
        )
        location_frame = pd.DataFrame([{"id": 9, "title": "WFA03", "northing": 51, "easting": 2}])
        service = ResultsService(
            repository=StubLocationRepository(pd.DataFrame(), location_frame),
        )
        ctx = service._plot_context([record], plot_type="geo")
        assert "location_frame" in ctx
        assert len(ctx["location_frame"]) == 1


class TestModuleLevelFunctions:
    def _make_stub_service(self) -> ResultsService:
        """Build a service backed by a stub with one histogram result."""
        analysis = WindSpeedHistogram()
        results = analysis.to_results(
            {
                "series": [
                    {
                        "title": "Design",
                        "scope_label": "Site",
                        "site_id": 1,
                        "bins": [(0.0, 1.0), (1.0, 2.0)],
                        "values": [1.0, 2.0],
                    }
                ]
            }
        )
        frame = pd.DataFrame([r.to_record_payload(analysis_id=11) for r in results])
        return ResultsService(repository=StubRepository(frame))

    def test_module_get_results(self) -> None:
        service = self._make_stub_service()
        df = module_get_results("WindSpeedHistogram", service=service)
        assert "bin_left" in df.columns

    def test_module_plot_results(self) -> None:
        service = self._make_stub_service()
        response = module_plot_results("WindSpeedHistogram", service=service)
        assert response.html
