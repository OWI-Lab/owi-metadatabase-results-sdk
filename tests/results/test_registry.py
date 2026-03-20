"""Tests for the analysis registry."""

from owi.metadatabase.results import default_registry


def test_registry_contains_built_in_analyses() -> None:
    assert "LifetimeDesignFrequencies" in default_registry.names()
    assert "WindSpeedHistogram" in default_registry.names()
    assert "LifetimeDesignVerification" in default_registry.names()
