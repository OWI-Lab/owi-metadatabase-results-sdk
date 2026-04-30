"""Tests for lifetime design frequencies analysis."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from owi.metadatabase.results import LifetimeDesignFrequencies
from owi.metadatabase.results.analyses.lifetime_design_frequencies import (
    FrequencyRow,
    LifetimeDesignFrequenciesInput,
)
from owi.metadatabase.results.models import AnalysisKind, ResultScope


class TestFrequencyRow:
    def test_alias_fields(self) -> None:
        row = FrequencyRow(turbine="A01", reference="INFL", FA1=0.34, SS1=0.35)  # ty: ignore[unknown-argument]
        assert row.fa1 == 0.34
        assert row.ss1 == 0.35
        assert row.metric_values() == {"FA1": 0.34, "SS1": 0.35}

    def test_optional_metrics(self) -> None:
        row = FrequencyRow(turbine="A01", reference="INFL")
        assert row.fa1 is None
        assert row.ss1 is None
        assert row.fa2 is None
        assert row.ss2 is None
        assert row.metric_values() == {}

    def test_dynamic_metrics_are_supported(self) -> None:
        row = FrequencyRow(turbine="A01", reference="INFL", FA3=0.36, tors1=0.42)  # ty: ignore[unknown-argument]
        assert row.metric_values() == {"FA3": 0.36, "TORS1": 0.42}

    def test_invalid_dynamic_metric_value_raises(self) -> None:
        with pytest.raises(ValidationError, match="float"):
            FrequencyRow(turbine="A01", reference="INFL", FA3="not-a-number")  # ty: ignore[unknown-argument]


class TestLifetimeDesignFrequenciesInput:
    def test_requires_at_least_one_row(self) -> None:
        with pytest.raises(ValidationError):
            LifetimeDesignFrequenciesInput(rows=[])


class TestLifetimeDesignFrequencies:
    def test_class_attributes(self) -> None:
        analysis = LifetimeDesignFrequencies()
        assert analysis.analysis_name == "LifetimeDesignFrequencies"
        assert analysis.analysis_kind == AnalysisKind.COMPARISON.value
        assert analysis.result_scope == ResultScope.LOCATION.value

    def test_validate_inputs_dict(self) -> None:
        analysis = LifetimeDesignFrequencies()
        result = analysis.validate_inputs({"rows": [{"turbine": "A", "reference": "R", "FA1": 0.3}]})
        assert isinstance(result, LifetimeDesignFrequenciesInput)

    def test_validate_inputs_passthrough(self) -> None:
        analysis = LifetimeDesignFrequencies()
        inp = LifetimeDesignFrequenciesInput(rows=[FrequencyRow(turbine="A", reference="R", FA1=0.3)])  # ty: ignore[unknown-argument]
        assert analysis.validate_inputs(inp) is inp

    def test_compute_produces_long_table(self) -> None:
        analysis = LifetimeDesignFrequencies()
        df = analysis.compute({"rows": [{"turbine": "A01", "reference": "INFL", "FA1": 0.34, "SS1": 0.35}]})
        assert "series_name" in df.columns
        assert "metric" in df.columns
        assert len(df) == 2

    def test_to_results_groups_by_turbine_metric(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {
                "rows": [
                    {"turbine": "A01", "reference": "INFL", "FA1": 0.34, "location_id": 1},
                    {"turbine": "A01", "reference": "ACTU", "FA1": 0.33, "location_id": 1},
                ]
            }
        )
        assert len(results) == 1
        assert results[0].short_description == "A01 - FA1"
        assert len(results[0].vectors[0].values) == 2

    def test_to_results_multiple_metrics(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {
                "rows": [
                    {"turbine": "A01", "reference": "INFL", "FA1": 0.34, "SS1": 0.35, "location_id": 1},
                ]
            }
        )
        assert len(results) == 2
        descriptions = {r.short_description for r in results}
        assert descriptions == {"A01 - FA1", "A01 - SS1"}

    def test_to_results_dynamic_metrics(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {
                "rows": [
                    {"turbine": "A01", "reference": "INFL", "FA3": 0.34, "TORS1": 0.35, "location_id": 1},
                ]
            }
        )
        descriptions = {r.short_description for r in results}
        assert descriptions == {"A01 - FA3", "A01 - TORS1"}
        vector_names = {r.vectors[1].name for r in results}
        assert vector_names == {"FA3", "TORS1"}

    def test_from_results_roundtrip(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {
                "rows": [
                    {"turbine": "A01", "reference": "INFL", "FA1": 0.34, "location_id": 1},
                    {"turbine": "A01", "reference": "ACTU", "FA1": 0.33, "location_id": 1},
                ]
            }
        )
        df = analysis.from_results(results)
        assert set(df["reference"]) == {"INFL", "ACTU"}
        assert set(df["turbine"]) == {"A01"}

    def test_from_results_roundtrip_dynamic_metric(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {
                "rows": [
                    {"turbine": "A01", "reference": "INFL", "FA3": 0.34, "location_id": 1},
                    {"turbine": "A01", "reference": "ACTU", "FA3": 0.33, "location_id": 1},
                ]
            }
        )
        df = analysis.from_results(results)
        assert set(df["metric"]) == {"FA3"}
        assert set(df["reference"]) == {"INFL", "ACTU"}

    def test_to_results_stores_reference_labels(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {
                "rows": [
                    {"turbine": "A01", "reference": "INFL", "FA1": 0.34, "location_id": 1},
                    {"turbine": "A01", "reference": "ACTU", "FA1": 0.33, "location_id": 1},
                ]
            }
        )
        assert results[0].data_additional["reference_labels"] == ["INFL", "ACTU"]

    def test_split_series_description(self) -> None:
        turbine, metric = LifetimeDesignFrequencies._split_series_description("WFA03 - FA1")
        assert turbine == "WFA03"
        assert metric == "FA1"

    def test_split_series_description_no_separator(self) -> None:
        turbine, metric = LifetimeDesignFrequencies._split_series_description("NoSeparator")
        assert turbine == "NoSeparator"
        assert metric is None

    def test_to_results_site_scope_when_no_location(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {
                "rows": [
                    {"turbine": "A01", "reference": "INFL", "FA1": 0.34, "site_id": 1},
                ]
            }
        )
        assert results[0].result_scope == ResultScope.SITE
        assert results[0].site_id == 1

    def test_plot_unsupported_type_raises(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {"rows": [{"turbine": "A01", "reference": "INFL", "FA1": 0.34, "location_id": 1}]}
        )
        with pytest.raises(ValueError, match="Unsupported plot_type"):
            from owi.metadatabase.results.models import PlotRequest

            analysis.plot(results, request=PlotRequest(analysis_name="LDF", plot_type="unknown"))

    def test_plot_geo_requires_location_frame(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {"rows": [{"turbine": "A01", "reference": "INFL", "FA1": 0.34, "location_id": 1}]}
        )
        with pytest.raises(ValueError, match="Location coordinates"):
            from owi.metadatabase.results.models import PlotRequest

            analysis.plot(results, request=PlotRequest(analysis_name="LDF", plot_type="geo"))

    def test_reference_labels_from_result_string_value(self) -> None:
        analysis = LifetimeDesignFrequencies()
        results = analysis.to_results(
            {"rows": [{"turbine": "A01", "reference": "INFL", "FA1": 0.34, "location_id": 1}]}
        )
        result = results[0].model_copy(update={"data_additional": {"reference_labels": "SINGLE"}})
        labels = analysis._reference_labels_from_result(result)
        assert labels == ["SINGLE"]
