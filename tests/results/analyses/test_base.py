"""Tests for BaseAnalysis mixin."""

from __future__ import annotations

import pytest

from owi.metadatabase.results.analyses.base import BaseAnalysis


class TestBaseAnalysis:
    def test_default_attributes(self) -> None:
        base = BaseAnalysis()
        assert base.analysis_name == "base"
        assert base.analysis_kind == "comparison"
        assert base.result_scope == "site"
        assert base.default_plot_type == "comparison"

    def test_validate_inputs_passthrough(self) -> None:
        base = BaseAnalysis()
        payload = {"key": "value"}
        assert base.validate_inputs(payload) is payload

    def test_compute_raises(self) -> None:
        base = BaseAnalysis()
        with pytest.raises(NotImplementedError):
            base.compute({"key": "value"})

    def test_to_results_raises(self) -> None:
        base = BaseAnalysis()
        with pytest.raises(NotImplementedError):
            base.to_results({"key": "value"})

    def test_from_results_raises(self) -> None:
        base = BaseAnalysis()
        with pytest.raises(NotImplementedError):
            base.from_results([])
