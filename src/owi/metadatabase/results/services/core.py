"""High-level services for retrieving and plotting results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import pandas as pd
from owi.metadatabase.locations.io import LocationsAPI  # ty: ignore[unresolved-import]

from ..io import ResultsAPI
from ..models import PlotRequest, PlotResponse, ResultQuery, ResultSeries
from ..plotting.definitions import PlotSourceData, PlotSourceSpec
from ..plotting.registry import get_plot_definition
from ..protocols import AnalysisRegistryProtocol, PlotDefinitionProtocol, ResultsRepositoryProtocol
from ..registry import default_registry
from ..serializers import DjangoResultSerializer


class ApiResultsRepository:
    """Repository adapter built on top of ResultsAPI."""

    def __init__(self, api: ResultsAPI | None = None) -> None:
        self.api = api or ResultsAPI(token="dummy")

    def list_analyses(self, name: str | None = None, **kwargs: Any) -> pd.DataFrame:
        """Retrieve analysis rows from the backend."""
        return self.api.list_analyses(name=name, **kwargs)["data"]

    def list_results(self, query: ResultQuery) -> pd.DataFrame:
        """Retrieve raw result rows from the backend."""
        return self.api.list_results(**query.to_backend_filters())["data"]

    def create_analysis(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create an analysis row."""
        return self.api.create_analysis(dict(payload))

    def create_result(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create a single result row."""
        return self.api.create_result(dict(payload))

    def create_results_bulk(self, payloads: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        """Create multiple result rows."""
        return self.api.create_results_bulk([dict(payload) for payload in payloads])

    def create_or_update_results_bulk(self, payloads: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        """Create missing result rows and patch existing ones."""
        return self.api.create_or_update_results_bulk([dict(payload) for payload in payloads])

    def update_result(self, result_id: int, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Patch a single result row."""
        return self.api.update_result(result_id, dict(payload))

    def get_location_frame(self, location_ids: Sequence[int]) -> pd.DataFrame:
        """Retrieve location metadata required by map-oriented plots."""
        if not location_ids:
            return pd.DataFrame(columns=["id", "title", "northing", "easting"])
        location_api = LocationsAPI(api_root=self.api.base_api_root, **self.api._auth_kwargs())
        assetlocations = location_api.get_assetlocations()["data"]
        if assetlocations.empty or "id" not in assetlocations.columns:
            return pd.DataFrame(columns=["id", "title", "northing", "easting"])
        location_frame = assetlocations[assetlocations["id"].isin(location_ids)].copy()
        columns = [column for column in ["id", "title", "northing", "easting"] if column in location_frame.columns]
        return location_frame.loc[:, columns]


class ResultsService:
    """Facade for validated retrieval and plotting.

    Parameters
    ----------
    repository : ResultsRepositoryProtocol, optional
        Repository instance to use for data access. This means that the service
        does not depend on a specific repository implementation, and the default
        is a simple API adapter. Custom repositories can be injected for testing
        or to support alternative backends.
    registry : AnalysisRegistryProtocol, optional
        Analysis registry to use for looking up analysis definitions. The default
        is a simple in-memory registry pre-populated with the built-in analyses.
        Different registries can be injected to support custom analyses or
        alternative lookup mechanisms.

    Examples
    --------
    >>> service = ResultsService()
    >>> service.get_results("WindSpeedHistogram", filters={"location_id": 123})
    pd.DataFrame(...)
    >>> service.plot_results("WindSpeedHistogram",
    ...                      filters={"location_id": 123},
    ...                      plot_type="histogram")
    PlotResponse(...)
    """

    def __init__(
        self,
        repository: ResultsRepositoryProtocol | None = None,
        registry: AnalysisRegistryProtocol | None = None,
    ) -> None:
        self.repository = repository or ApiResultsRepository()
        self.registry = registry or default_registry
        self.serializer = DjangoResultSerializer()

    def _coerce_query(
        self,
        analysis_name: str,
        filters: ResultQuery | Mapping[str, Any] | None = None,
    ) -> ResultQuery:
        """Build a concrete query model from loose filter input."""
        query = (
            filters if isinstance(filters, ResultQuery) else ResultQuery(analysis_name=analysis_name, **(filters or {}))
        )
        if query.analysis_name is None:
            query = query.model_copy(update={"analysis_name": analysis_name})
        return query

    def deserialize_result_series(
        self,
        raw_data: Sequence[Mapping[str, Any]] | pd.DataFrame,
    ) -> list[ResultSeries]:
        """Deserialize raw backend rows into typed result series."""
        if isinstance(raw_data, pd.DataFrame):
            raw_records = cast(list[dict[str, Any]], raw_data.to_dict(orient="records"))
        else:
            raw_records = [dict(row) for row in raw_data]
        return [self.serializer.from_mapping(row) for row in raw_records]

    def get_result_series(
        self,
        analysis_name: str,
        filters: ResultQuery | Mapping[str, Any] | None = None,
    ) -> list[ResultSeries]:
        """Fetch and deserialize typed result series for the given analysis."""
        query = self._coerce_query(analysis_name, filters)
        frame = self.repository.list_results(query)
        return self.deserialize_result_series(frame)

    def get_location_frame(self, location_ids: Sequence[int]) -> pd.DataFrame:
        """Return location metadata for the given backend location identifiers."""
        columns = ["id", "title", "northing", "easting"]
        if not location_ids:
            return pd.DataFrame(columns=columns)
        get_location_frame = getattr(self.repository, "get_location_frame", None)
        if not callable(get_location_frame):
            return pd.DataFrame(columns=columns)
        location_frame = get_location_frame(location_ids)
        if not isinstance(location_frame, pd.DataFrame):
            return pd.DataFrame(columns=columns)
        if location_frame.empty:
            return pd.DataFrame(columns=columns)
        available_columns = [column for column in columns if column in location_frame.columns]
        selected_frame = cast(pd.DataFrame, location_frame.loc[:, available_columns])
        return selected_frame.copy()

    def get_results(self, analysis_name: str, filters: ResultQuery | Mapping[str, Any] | None = None) -> pd.DataFrame:
        """Return normalized analysis data for the given analysis."""
        records = self.get_result_series(analysis_name, filters)
        analysis = self.registry.get(analysis_name)
        return analysis.from_results(records)

    def _plot_context(
        self,
        records: Sequence[ResultSeries],
        *,
        plot_type: str | None,
    ) -> dict[str, Any]:
        """Build optional context required by specific plot types."""
        context: dict[str, Any] = {}
        if plot_type not in {"geo", "map"}:
            return context
        location_ids = sorted({record.location_id for record in records if record.location_id is not None})
        location_frame = self.get_location_frame(location_ids)
        if not location_frame.empty:
            context["location_frame"] = location_frame
        return context

    def _plot_source_data(
        self,
        source_spec: PlotSourceSpec,
        *,
        owner_analysis_name: str,
        query: ResultQuery,
    ) -> PlotSourceData:
        """Fetch and normalize one named plot source."""
        source_query = source_spec.build_query(query, owner_analysis_name)
        source_records = self.get_result_series(source_spec.analysis_name, source_query)
        source_analysis = self.registry.get(source_spec.analysis_name)
        return PlotSourceData(
            key=source_spec.key,
            analysis_name=source_spec.analysis_name,
            query=source_query,
            records=source_records,
            frame=source_analysis.from_results(source_records),
        )

    def _plot_defined_results(
        self,
        definition: PlotDefinitionProtocol,
        *,
        owner_analysis_name: str,
        query: ResultQuery,
        plot_type: str | None,
    ) -> PlotResponse:
        """Render a plot assembled from one or more named sources."""
        source_specs = tuple(definition.build_sources(query, owner_analysis_name))
        sources_by_key = {
            source_spec.key: self._plot_source_data(
                source_spec,
                owner_analysis_name=owner_analysis_name,
                query=query,
            )
            for source_spec in source_specs
        }
        plot_request = PlotRequest(
            analysis_name=owner_analysis_name,
            filters=query.model_dump(),
            plot_type=plot_type,
            context={
                "source_keys": list(sources_by_key),
                "source_analysis_names": [source_data.analysis_name for source_data in sources_by_key.values()],
            },
        )
        return definition.render(sources_by_key, plot_request)

    def plot_results(
        self,
        analysis_name: str,
        filters: ResultQuery | Mapping[str, Any] | None = None,
        *,
        plot_type: str | None = None,
    ) -> PlotResponse:
        """Render a chart for the requested analysis."""
        query = self._coerce_query(analysis_name, filters)
        plot_definition = get_plot_definition(analysis_name, plot_type)
        if plot_definition is not None:
            return self._plot_defined_results(
                plot_definition,
                owner_analysis_name=analysis_name,
                query=query,
                plot_type=plot_type,
            )
        records = self.get_result_series(analysis_name, query)
        analysis = self.registry.get(analysis_name)
        plot_request = PlotRequest(
            analysis_name=analysis_name,
            filters=query.model_dump(),
            plot_type=plot_type,
            context=self._plot_context(records, plot_type=plot_type),
        )
        return analysis.plot(records, request=plot_request)


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
    *,
    plot_type: str | None = None,
    service: ResultsService | None = None,
) -> PlotResponse:
    """Return a plotted chart using the default service."""
    return (service or ResultsService()).plot_results(analysis_name, filters, plot_type=plot_type)
