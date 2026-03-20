"""High-level services for retrieving and plotting results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import pandas as pd

from .io import ResultsAPI
from .models import PlotRequest, PlotResponse, ResultQuery, ResultSeries
from .plotting import get_plot_strategy
from .protocols import AnalysisRegistryProtocol, ResultsRepositoryProtocol
from .registry import default_registry
from .serializers import DjangoResultSerializer


class ApiResultsRepository:
    """Repository adapter built on top of ResultsAPI."""

    def __init__(self, api: ResultsAPI | None = None) -> None:
        self.api = api or ResultsAPI(token="dummy")

    def list_results(self, query: ResultQuery) -> pd.DataFrame:
        """Retrieve raw result rows from the backend."""
        return self.api.list_results(**query.to_backend_filters())["data"]

    def create_analysis(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create an analysis row."""
        return self.api.create_analysis(dict(payload))

    def create_results_bulk(self, payloads: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        """Create multiple result rows."""
        return self.api.create_results_bulk([dict(payload) for payload in payloads])


class ResultsService:
    """Facade for validated retrieval and plotting."""

    def __init__(
        self,
        repository: ResultsRepositoryProtocol | None = None,
        registry: AnalysisRegistryProtocol | None = None,
    ) -> None:
        self.repository = repository or ApiResultsRepository()
        self.registry = registry or default_registry
        self.serializer = DjangoResultSerializer()

    def get_results(self, analysis_name: str, filters: ResultQuery | Mapping[str, Any] | None = None) -> pd.DataFrame:
        """Return normalized analysis data for the given analysis."""
        query = (
            filters if isinstance(filters, ResultQuery) else ResultQuery(analysis_name=analysis_name, **(filters or {}))
        )
        if query.analysis_name is None:
            query = query.model_copy(update={"analysis_name": analysis_name})
        frame = self.repository.list_results(query)
        raw_records = cast(list[dict[str, Any]], frame.to_dict(orient="records"))
        records = [self.serializer.from_mapping(row) for row in raw_records]
        analysis = self.registry.get(analysis_name)
        return analysis.from_results(records)

    def plot_results(self, analysis_name: str, filters: ResultQuery | Mapping[str, Any] | None = None) -> PlotResponse:
        """Render a chart for the requested analysis."""
        query = (
            filters if isinstance(filters, ResultQuery) else ResultQuery(analysis_name=analysis_name, **(filters or {}))
        )
        if query.analysis_name is None:
            query = query.model_copy(update={"analysis_name": analysis_name})
        frame = self.repository.list_results(query)
        raw_records = cast(list[dict[str, Any]], frame.to_dict(orient="records"))
        records: list[ResultSeries] = [self.serializer.from_mapping(row) for row in raw_records]
        analysis = self.registry.get(analysis_name)
        plot_request = PlotRequest(analysis_name=analysis_name, filters=query)
        plot_strategy = get_plot_strategy(analysis.default_plot_type)
        return analysis.plot(records, request=plot_request, plot_strategy=plot_strategy)


def get_results(
    analysis_name: str,
    filters: ResultQuery | Mapping[str, Any] | None = None,
    service: ResultsService | None = None,
) -> pd.DataFrame:
    """Return normalized analysis data using the default service."""
    return (service or ResultsService()).get_results(analysis_name, filters)


def plot_results(
    analysis_name: str,
    filters: ResultQuery | Mapping[str, Any] | None = None,
    service: ResultsService | None = None,
) -> PlotResponse:
    """Return a plotted chart using the default service."""
    return (service or ResultsService()).plot_results(analysis_name, filters)
