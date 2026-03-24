"""Tests for lifetime design verification analysis."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from owi.metadatabase.results.analyses.lifetime_design_verification import (
    LifetimeDesignVerification,
    LifetimeDesignVerificationInput,
    VerificationRow,
)
from owi.metadatabase.results.models import AnalysisKind, ResultScope


class TestVerificationRow:
    def test_alias_fields(self) -> None:
        row = VerificationRow(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            turbine="A01",
            FA1=0.356,  # ty: ignore[unknown-argument]
        )
        assert row.fa1 == 0.356

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            VerificationRow(
                timestamp=datetime(2024, 1, 1),
                turbine="A01",
                FA1=0.356,  # ty: ignore[unknown-argument]
            )


class TestLifetimeDesignVerification:
    def test_class_attributes(self) -> None:
        analysis = LifetimeDesignVerification()
        assert analysis.analysis_name == "LifetimeDesignVerification"
        assert analysis.analysis_kind == AnalysisKind.TIME_SERIES.value
        assert analysis.default_plot_type == "time_series"

    def test_validate_inputs_dict(self) -> None:
        analysis = LifetimeDesignVerification()
        result = analysis.validate_inputs(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                    }
                ]
            }
        )
        assert isinstance(result, LifetimeDesignVerificationInput)

    def test_validate_inputs_passthrough(self) -> None:
        analysis = LifetimeDesignVerification()
        inp = LifetimeDesignVerificationInput(
            rows=[
                VerificationRow(
                    timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    turbine="A01",
                    FA1=0.356,  # ty: ignore[unknown-argument]
                )
            ]
        )
        assert analysis.validate_inputs(inp) is inp

    def test_compute_produces_long_table(self) -> None:
        analysis = LifetimeDesignVerification()
        df = analysis.compute(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "SS1": 0.357,
                    }
                ]
            }
        )
        assert "series_name" in df.columns
        assert "metric" in df.columns
        assert len(df) == 2

    def test_to_results_groups_by_turbine_metric(self) -> None:
        analysis = LifetimeDesignVerification()
        results = analysis.to_results(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "location_id": 5,
                    },
                    {
                        "timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.355,
                        "location_id": 5,
                    },
                ]
            }
        )
        assert len(results) == 1
        assert results[0].short_description == "A01 - FA1"
        assert len(results[0].vectors[0].values) == 2

    def test_to_results_stores_epoch_timestamps(self) -> None:
        analysis = LifetimeDesignVerification()
        results = analysis.to_results(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "location_id": 5,
                    }
                ]
            }
        )
        epoch = results[0].vectors[0].values[0]
        assert epoch == datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()

    def test_from_results_roundtrip(self) -> None:
        analysis = LifetimeDesignVerification()
        results = analysis.to_results(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "location_id": 5,
                    },
                    {
                        "timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.355,
                        "location_id": 5,
                    },
                ]
            }
        )
        df = analysis.from_results(results)
        assert len(df) == 2
        assert set(df["turbine"]) == {"A01"}
        assert all(df["x"].str.startswith("2024-01-0"))

    def test_to_results_site_scope_when_no_location(self) -> None:
        analysis = LifetimeDesignVerification()
        results = analysis.to_results(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "site_id": 1,
                    }
                ]
            }
        )
        assert results[0].result_scope == ResultScope.SITE

    def test_to_results_multiple_metrics(self) -> None:
        analysis = LifetimeDesignVerification()
        results = analysis.to_results(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "SS1": 0.357,
                        "location_id": 5,
                    }
                ]
            }
        )
        assert len(results) == 2
        descriptions = {r.short_description for r in results}
        assert descriptions == {"A01 - FA1", "A01 - SS1"}

    def test_to_results_sorts_by_timestamp(self) -> None:
        analysis = LifetimeDesignVerification()
        results = analysis.to_results(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 3, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "location_id": 5,
                    },
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.355,
                        "location_id": 5,
                    },
                ]
            }
        )
        timestamps = results[0].vectors[0].values
        assert timestamps == sorted(timestamps)

    def test_data_additional_contains_series_key(self) -> None:
        analysis = LifetimeDesignVerification()
        results = analysis.to_results(
            {
                "rows": [
                    {
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "turbine": "A01",
                        "FA1": 0.356,
                        "location_id": 5,
                    }
                ]
            }
        )
        assert results[0].data_additional["series_key"] == "A01:FA1"
