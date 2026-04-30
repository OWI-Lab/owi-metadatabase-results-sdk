"""Tests for registered custom plot definitions."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from owi.metadatabase.results.models import ResultQuery
from owi.metadatabase.results.plotting.definitions import PlotSourceData
from owi.metadatabase.results.plotting.frequency_verification import (
    assemble_frequency_verification_comparison_frame,
)
from owi.metadatabase.results.plotting.registry import get_plot_definition


def test_get_plot_definition_supports_cross_analysis_plot_without_owner() -> None:
    definition = get_plot_definition("cross_analysis_fleetwide")

    assert definition is not None


def test_get_plot_definition_supports_both_compatible_analysis_names() -> None:
    verification_definition = get_plot_definition(
        "cross_analysis_fleetwide",
        analysis_name="LifetimeDesignVerification",
    )
    frequency_definition = get_plot_definition(
        "cross_analysis_fleetwide",
        analysis_name="LifetimeDesignFrequencies",
    )

    assert verification_definition is not None
    assert frequency_definition is not None
    assert verification_definition is frequency_definition


def test_get_plot_definition_rejects_unsupported_analysis_name() -> None:
    with pytest.raises(ValueError, match="does not support analysis"):
        get_plot_definition("cross_analysis_fleetwide", analysis_name="WindSpeedHistogram")


def test_frequency_verification_plot_definition_builds_named_sources() -> None:
    definition = get_plot_definition("cross_analysis_fleetwide")
    assert definition is not None

    query = ResultQuery(
        location_id=9,
        backend_filters={"analysis__id": 321, "analysis__name": "ignored", "foo": "bar"},
    )
    sources = tuple(definition.build_sources(query))

    assert [source.key for source in sources] == ["frequency", "verification"]

    frequency_query = sources[0].build_query(query)
    verification_query = sources[1].build_query(query)

    assert frequency_query.analysis_name == "LifetimeDesignFrequencies"
    assert frequency_query.analysis_id is None
    assert frequency_query.backend_filters == {"foo": "bar"}

    assert verification_query.analysis_name == "LifetimeDesignVerification"
    assert verification_query.analysis_id is None
    assert verification_query.backend_filters == {"foo": "bar"}


def test_assemble_frequency_verification_comparison_frame_from_named_sources() -> None:
    frame = assemble_frequency_verification_comparison_frame(
        {
            "frequency": PlotSourceData(
                key="frequency",
                analysis_name="LifetimeDesignFrequencies",
                query=ResultQuery(analysis_name="LifetimeDesignFrequencies"),
                records=[],
                frame=pd.DataFrame(
                    [
                        {
                            "x": "INFL",
                            "y": 2.4123,
                            "series_name": "WFA03 - FA1",
                            "turbine": "WFA03",
                            "metric": "FA1",
                            "reference": "INFL",
                        },
                        {
                            "x": "ACTU",
                            "y": 1.9184,
                            "series_name": "WFA03 - FA1",
                            "turbine": "WFA03",
                            "metric": "FA1",
                            "reference": "ACTU",
                        },
                    ]
                ),
            ),
            "verification": PlotSourceData(
                key="verification",
                analysis_name="LifetimeDesignVerification",
                query=ResultQuery(analysis_name="LifetimeDesignVerification"),
                records=[],
                frame=pd.DataFrame(
                    [
                        {
                            "x": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
                            "y": 2.5517,
                            "series_name": "WFA03 - FA1",
                            "turbine": "WFA03",
                            "metric": "FA1",
                        }
                    ]
                ),
            ),
        }
    )

    assert list(frame.columns) == [
        "asset",
        "metric",
        "y",
        "timestamp_label",
        "timestamp_epoch",
        "hover_name",
        "reference_label",
        "reference_order",
    ]

    frequency_rows = frame[frame["reference_label"].notna()].reset_index(drop=True)
    verification_rows = frame[frame["timestamp_epoch"].notna()].reset_index(drop=True)

    assert list(frequency_rows["reference_label"]) == ["INFL", "ACTU"]
    assert list(frequency_rows["reference_order"]) == [1, 2]
    assert set(frequency_rows["metric"]) == {"FA1"}

    assert len(verification_rows) == 1
    assert verification_rows.loc[0, "asset"] == "WFA03"
    assert verification_rows.loc[0, "hover_name"] == "WFA03"
    assert verification_rows.loc[0, "metric"] == "FA1"
    assert verification_rows.loc[0, "timestamp_label"].startswith("2024-01-01T00:00:00")
