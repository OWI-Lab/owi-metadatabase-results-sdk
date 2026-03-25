"""Tests for endpoint configuration."""

import pytest

from owi.metadatabase.results.endpoints import DEFAULT_RESULTS_ENDPOINTS, ResultsEndpoints


def test_default_endpoints_api_subdir() -> None:
    assert DEFAULT_RESULTS_ENDPOINTS.api_subdir == "/results/routes/"


def test_mutation_path_appends_trailing_slash() -> None:
    endpoints = ResultsEndpoints()
    assert endpoints.mutation_path("analysis") == "analysis/"


def test_mutation_path_does_not_double_slash() -> None:
    endpoints = ResultsEndpoints()
    assert endpoints.mutation_path("analysis/") == "analysis/"


def test_detail_path_format() -> None:
    endpoints = ResultsEndpoints()
    assert endpoints.detail_path("result", 42) == "result/42/"


def test_detail_path_strips_trailing_slash_before_id() -> None:
    endpoints = ResultsEndpoints()
    assert endpoints.detail_path("result/", 7) == "result/7/"


def test_frozen_dataclass_prevents_mutation() -> None:
    endpoints = ResultsEndpoints()
    with pytest.raises(AttributeError):
        object.__setattr__(endpoints, "api_subdir", "/other/")


def test_custom_endpoints() -> None:
    endpoints = ResultsEndpoints(api_subdir="/custom/", analysis="custom_analysis")
    assert endpoints.api_subdir == "/custom/"
    assert endpoints.mutation_path("custom_analysis") == "custom_analysis/"
