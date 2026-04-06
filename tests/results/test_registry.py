"""Tests for the analysis registry."""

import pytest

from owi.metadatabase.results.registry import AnalysisRegistry, default_registry


def test_registry_contains_built_in_analyses() -> None:
    assert "LifetimeDesignFrequencies" in default_registry.names()
    assert "WindSpeedHistogram" in default_registry.names()
    assert "LifetimeDesignVerification" in default_registry.names()


def test_registry_get_unknown_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown analysis"):
        default_registry.get("NonExistentAnalysis")


def test_registry_get_returns_instance() -> None:
    analysis = default_registry.get("WindSpeedHistogram")
    assert analysis.analysis_name == "WindSpeedHistogram"


def test_registry_names_sorted() -> None:
    names = default_registry.names()
    assert names == sorted(names)


def test_fresh_registry_is_empty() -> None:
    registry = AnalysisRegistry()
    assert registry.names() == []


def test_register_analysis_decorator() -> None:
    registry = AnalysisRegistry()

    class DummyAnalysis:
        analysis_name = "DummyAnalysis"

    registry.register(DummyAnalysis)
    assert "DummyAnalysis" in registry.names()
    instance = registry.get("DummyAnalysis")
    assert instance.analysis_name == "DummyAnalysis"
