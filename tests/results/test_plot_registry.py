"""Tests for registered custom plot definitions."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from owi.metadatabase.results.models import ResultQuery
from owi.metadatabase.results.plotting.definitions import PlotSourceData
from owi.metadatabase.results.plotting.frequency_verification import (
    assemble_frequency_verification_comparison_frame,
)
from owi.metadatabase.results.plotting.registry import get_plot_definition


def test_get_plot_definition_supports_both_owner_aliases() -> None:
    verification_definition = get_plot_definition("LifetimeDesignVerification", "assembled")
    frequency_definition = get_plot_definition("LifetimeDesignFrequencies", "assembled")

    assert verification_definition is not None
    assert frequency_definition is not None
    assert verification_definition is frequency_definition


def test_frequency_verification_plot_definition_builds_named_sources() -> None:
    definition = get_plot_definition("LifetimeDesignVerification", "assembled")
    assert definition is not None

    query = ResultQuery(
        analysis_name="LifetimeDesignVerification",
        analysis_id=999,
        backend_filters={"analysis__id": 321, "analysis__name": "ignored", "foo": "bar"},
    )
    sources = tuple(definition.build_sources(query, "LifetimeDesignVerification"))

    assert [source.key for source in sources] == ["frequency", "verification"]

    frequency_query = sources[0].build_query(query, "LifetimeDesignVerification")
    verification_query = sources[1].build_query(query, "LifetimeDesignVerification")

    assert frequency_query.analysis_name == "LifetimeDesignFrequencies"
    assert frequency_query.analysis_id is None
    assert frequency_query.backend_filters == {"foo": "bar"}

    assert verification_query.analysis_name == "LifetimeDesignVerification"
    assert verification_query.analysis_id == 999
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
