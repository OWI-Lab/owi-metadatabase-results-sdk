"""Endpoint configuration for the results extension."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResultsEndpoints:
    """Centralized route names for the results backend."""

    api_subdir: str = "/results/routes/"
    analysis: str = "analysis"
    result: str = "result"
    result_bulk: str = "result/bulk"

    def mutation_path(self, endpoint: str) -> str:
        """Return a mutation endpoint path with a trailing slash."""
        return endpoint.rstrip("/") + "/"


DEFAULT_RESULTS_ENDPOINTS = ResultsEndpoints()
