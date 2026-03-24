"""Protocols for the results extension."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from .models import PlotRequest, PlotResponse, ResultQuery, ResultSeries


@runtime_checkable
class ResultProtocol(Protocol):
    """Protocol for a single logical persisted result series."""

    analysis_name: str
    analysis_kind: str
    result_scope: str
    short_description: str
    site_id: int | None
    location_id: int | None

    def to_record_payload(self, analysis_id: int) -> dict[str, Any]:
        """Serialize the result to a Django-compatible payload."""


@runtime_checkable
class PlotStrategyProtocol(Protocol):
    """Protocol for chart rendering strategies."""

    chart_type: str

    def render(self, data: pd.DataFrame, request: PlotRequest) -> PlotResponse:
        """Render a chart from normalized analysis data."""


@runtime_checkable
class AnalysisProtocol(Protocol):
    """Protocol for executable analyses."""

    analysis_name: str
    analysis_kind: str
    result_scope: str
    default_plot_type: str

    def validate_inputs(self, payload: Any) -> Any:
        """Validate an analysis payload."""

    def compute(self, payload: Any) -> pd.DataFrame:
        """Compute or normalize analysis input data."""

    def to_results(self, payload: Any) -> list[ResultSeries]:
        """Convert a validated payload into persisted result objects."""

    def from_results(self, results: Sequence[ResultSeries]) -> pd.DataFrame:
        """Reconstruct normalized analysis data from persisted results."""

    def plot(
        self,
        results: Sequence[ResultSeries],
        request: PlotRequest | None = None,
        plot_strategy: PlotStrategyProtocol | None = None,
    ) -> PlotResponse:
        """Plot reconstructed results using the default or injected strategy."""


@runtime_checkable
class SerializerProtocol(Protocol):
    """Protocol for domain-to-backend serializers."""

    def to_payload(self, obj: Any) -> dict[str, Any]:
        """Serialize a validated domain object."""

    def from_mapping(self, mapping: Mapping[str, Any]) -> Any:
        """Deserialize a mapping into a validated domain object."""


@runtime_checkable
class AnalysisRegistryProtocol(Protocol):
    """Protocol for analysis registration and resolution."""

    def register(self, analysis_type: type[AnalysisProtocol]) -> type[AnalysisProtocol]:
        """Register an analysis implementation."""

    def get(self, analysis_name: str) -> AnalysisProtocol:
        """Return an analysis instance by name."""

    def names(self) -> list[str]:
        """Return the registered analysis names."""


@runtime_checkable
class ResultsRepositoryProtocol(Protocol):
    """Protocol for raw result persistence and retrieval."""

    def list_analyses(self, name: str | None = None, **kwargs: Any) -> pd.DataFrame:
        """Retrieve analysis rows from the backend."""

    def list_results(self, query: ResultQuery) -> pd.DataFrame:
        """Retrieve raw rows from the backend."""

    def create_analysis(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create an analysis record."""

    def create_result(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create a single result record."""

    def create_results_bulk(self, payloads: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        """Create multiple result records."""

    def update_result(self, result_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Patch a single result record."""

    def get_location_frame(self, location_ids: Sequence[int]) -> pd.DataFrame:
        """Return location metadata required by geo-oriented workflows."""


@runtime_checkable
class QueryServiceProtocol(Protocol):
    """Protocol for high-level result retrieval and plotting."""

    def deserialize_result_series(
        self,
        raw_data: Sequence[Mapping[str, Any]] | pd.DataFrame,
    ) -> list[ResultSeries]:
        """Deserialize raw backend rows into typed result series."""

    def get_result_series(
        self,
        analysis_name: str,
        filters: ResultQuery | Mapping[str, Any] | None = None,
    ) -> list[ResultSeries]:
        """Return typed persisted series for an analysis."""

    def get_location_frame(self, location_ids: Sequence[int]) -> pd.DataFrame:
        """Return location metadata required by geo-oriented workflows."""

    def get_results(self, analysis_name: str, filters: ResultQuery | Mapping[str, Any] | None = None) -> pd.DataFrame:
        """Return normalized analysis data."""

    def plot_results(
        self,
        analysis_name: str,
        filters: ResultQuery | Mapping[str, Any] | None = None,
        *,
        plot_type: str | None = None,
    ) -> PlotResponse:
        """Return a chart for normalized analysis data."""
