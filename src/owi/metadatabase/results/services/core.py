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
        analysis_name: str | None,
        filters: ResultQuery | Mapping[str, Any] | None = None,
    ) -> ResultQuery:
        """Build a concrete query model from loose filter input."""
        query = filters if isinstance(filters, ResultQuery) else ResultQuery(**(filters or {}))
        if analysis_name is not None and query.analysis_name is None:
            query = query.model_copy(update={"analysis_name": analysis_name})
        return query

    @staticmethod
    def _strip_analysis_filters(query: ResultQuery) -> ResultQuery:
        """Remove analysis-specific identifiers from a shared base query."""
        backend_filters = {
            key: value
            for key, value in query.backend_filters.items()
            if key not in {"analysis__id", "analysis__name"}
        }
        return query.model_copy(
            update={
                "analysis_name": None,
                "analysis_id": None,
                "backend_filters": backend_filters,
            }
        )

    def _merge_queries(
        self,
        base_query: ResultQuery,
        overrides: ResultQuery | Mapping[str, Any] | None,
    ) -> ResultQuery:
        """Merge source-specific overrides onto a shared base query."""
        if overrides is None:
            return base_query.model_copy()
        override_query = self._coerce_query(None, overrides)
        merged = base_query.model_dump()
        override_values = override_query.model_dump(exclude_none=True)
        merged.update({key: value for key, value in override_values.items() if key != "backend_filters"})
        merged["backend_filters"] = {
            **base_query.backend_filters,
            **override_query.backend_filters,
        }
        return ResultQuery(**merged)

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
        query: ResultQuery,
    ) -> PlotSourceData:
        """Fetch and normalize one named plot source."""
        source_query = source_spec.build_query(query)
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
        requested_analysis_name: str | None,
        filters: ResultQuery | Mapping[str, Any] | None,
        plot_type: str | None,
        source_filters: Mapping[str, ResultQuery | Mapping[str, Any]] | None,
    ) -> PlotResponse:
        """Render a plot built from one or more named sources."""
        raw_query = self._coerce_query(None, filters)
        if (
            requested_analysis_name is not None
            and raw_query.analysis_name is not None
            and raw_query.analysis_name != requested_analysis_name
        ):
            raise ValueError(
                "Conflicting analysis names were provided for the cross-analysis plot request: "
                f"{requested_analysis_name!r} and {raw_query.analysis_name!r}."
            )
        compatibility_analysis_name = requested_analysis_name or raw_query.analysis_name
        implicit_analysis_id = raw_query.analysis_id
        base_query = self._strip_analysis_filters(raw_query)
        source_specs = tuple(definition.build_sources(base_query))
        source_spec_by_key = {source_spec.key: source_spec for source_spec in source_specs}
        unexpected_source_filters = sorted(set(source_filters or {}).difference(source_spec_by_key))
        if unexpected_source_filters:
            unexpected = ", ".join(unexpected_source_filters)
            raise ValueError(f"Unknown source_filters keys for plot type {plot_type!r}: {unexpected}.")

        source_filter_overrides = dict(source_filters or {})
        if implicit_analysis_id is not None:
            if compatibility_analysis_name is None:
                raise ValueError(
                    "Cross-analysis plots require source_filters to disambiguate analysis_id values when "
                    "analysis_name is not provided."
                )
            matching_source_keys = [
                source_spec.key
                for source_spec in source_specs
                if source_spec.analysis_name == compatibility_analysis_name
            ]
            if len(matching_source_keys) != 1:
                raise ValueError(
                    "Cross-analysis plot compatibility could not map the provided analysis_name to exactly "
                    "one source."
                )
            matching_source_key = matching_source_keys[0]
            source_filter_overrides.setdefault(matching_source_key, {"analysis_id": implicit_analysis_id})

        sources_by_key = {
            source_spec.key: self._plot_source_data(
                source_spec,
                query=self._merge_queries(base_query, source_filter_overrides.get(source_spec.key)),
            )
            for source_spec in source_specs
        }
        request_analysis_name = compatibility_analysis_name or (plot_type or "custom_plot")
        plot_request = PlotRequest(
            analysis_name=request_analysis_name,
            filters=base_query.model_dump(),
            plot_type=plot_type,
            context={
                "source_keys": list(sources_by_key),
                "source_analysis_names": [source_data.analysis_name for source_data in sources_by_key.values()],
            },
        )
        return definition.render(sources_by_key, plot_request)

    def plot_results(
        self,
        analysis_name: str | None = None,
        filters: ResultQuery | Mapping[str, Any] | None = None,
        *,
        plot_type: str | None = None,
        source_filters: Mapping[str, ResultQuery | Mapping[str, Any]] | None = None,
    ) -> PlotResponse:
        """Render a chart for the requested analysis."""
        requested_analysis_name = analysis_name or self._coerce_query(None, filters).analysis_name
        plot_definition = get_plot_definition(plot_type, analysis_name=requested_analysis_name)
        if plot_definition is not None:
            return self._plot_defined_results(
                plot_definition,
                requested_analysis_name=requested_analysis_name,
                filters=filters,
                plot_type=plot_type,
                source_filters=source_filters,
            )
        if source_filters:
            raise ValueError("source_filters can only be used with registered cross-analysis plot types.")
        if requested_analysis_name is None:
            raise ValueError("analysis_name is required for plot types without a registered cross-analysis definition.")
        query = self._coerce_query(requested_analysis_name, filters)
        records = self.get_result_series(requested_analysis_name, query)
        analysis = self.registry.get(requested_analysis_name)
        plot_request = PlotRequest(
            analysis_name=requested_analysis_name,
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
    analysis_name: str | None = None,
    filters: ResultQuery | Mapping[str, Any] | None = None,
    *,
    plot_type: str | None = None,
    source_filters: Mapping[str, ResultQuery | Mapping[str, Any]] | None = None,
    service: ResultsService | None = None,
) -> PlotResponse:
    """Return a plotted chart using the default service."""
    return (service or ResultsService()).plot_results(
        analysis_name,
        filters,
        plot_type=plot_type,
        source_filters=source_filters,
    )
