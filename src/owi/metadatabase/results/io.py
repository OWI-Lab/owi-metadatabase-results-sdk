"""API client for the results extension.

This module exposes :class:`ResultsAPI` as the low-level entry point
for analysis and result persistence.

Examples
--------
>>> from owi.metadatabase.results import ResultsAPI
>>> isinstance(ResultsAPI(token="dummy"), ResultsAPI)
True
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
from owi.metadatabase._utils.exceptions import (  # ty: ignore[unresolved-import]
    APIConnectionError,
    InvalidParameterError,
)
from owi.metadatabase.io import API  # ty: ignore[unresolved-import]
from tqdm.auto import tqdm

from .endpoints import DEFAULT_RESULTS_ENDPOINTS, ResultsEndpoints


class ResultsAPI(API):
    """Low-level API client for the results extension.

    Parameters
    ----------
    api_subdir : str, default="/results/routes/"
        API sub-path appended to the base root.
    **kwargs
        Forwarded to :class:`owi.metadatabase.io.API`.

    Examples
    --------
    >>> api = ResultsAPI(token="dummy")
    >>> api.ping()
    'ok'
    """

    def __init__(self, api_subdir: str = DEFAULT_RESULTS_ENDPOINTS.api_subdir, **kwargs) -> None:
        self.endpoints: ResultsEndpoints = kwargs.pop("endpoints", DEFAULT_RESULTS_ENDPOINTS)
        super().__init__(**kwargs)
        self.base_api_root = self.api_root
        self.api_root = self.api_root + api_subdir

    def ping(self) -> str:
        """Return a basic health response.

        Examples
        --------
        >>> api = ResultsAPI(token="dummy")
        >>> api.ping()
        'ok'
        """
        return "ok"

    def list_analyses(self, name: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Return analysis metadata rows.

        Examples
        --------
        >>> from unittest.mock import patch
        >>> api = ResultsAPI(token="dummy")
        >>> result = (pd.DataFrame({'id': [1]}), {'existance': True})
        >>> with patch.object(ResultsAPI, 'process_data', return_value=result):
        ...     out = api.list_analyses(name='WindSpeedHistogram')
        >>> out['exists']
        True
        """
        url_params = dict(kwargs)
        if name is not None:
            url_params["name"] = name
        df, info = self.process_data(self.endpoints.analysis, url_params, "list")
        return {"data": df, "exists": info["existance"], "response": info.get("response")}

    def get_analysis(self, **kwargs: Any) -> dict[str, Any]:
        """Return a single analysis row.
        To make sure a single analysis is returned, use either the `id` parameter,
        or, for a more user-friendly query, the following combination of parameters
        that identify a single analysis, i.e., `name`, `model_definition__title`,
        `timestamp`, and `location__title`, since they uniquely identify an
        analysis in the backend.

        Examples
        --------
        >>> from unittest.mock import patch
        >>> api = ResultsAPI(token="dummy")
        >>> result = (pd.DataFrame({'id': [1]}), {'existance': True, 'id': 1})
        >>> with patch.object(ResultsAPI, 'process_data', return_value=result):
        ...     out = api.get_analysis(id=1)
        >>> out['exists']
        True
        >>> out['id']
        1

        >>> api = ResultsAPI(token="dummy")  # doctest: SKIP
        >>> analysis_params = {  # doctest: SKIP
        ...     'analysis__name': 'WindSpeedHistogram',  # doctest: SKIP
        ...     'model_definition__title': 'ERA5 reanalysis',  # doctest: SKIP
        ...     'timestamp': '2023-01-01T00:00:00Z',  # doctest: SKIP
        ...     'location__title': 'Test Location',  # doctest: SKIP
        ... }  # doctest: SKIP
        """
        if "timestamp" in kwargs and isinstance(kwargs["timestamp"], datetime.datetime):
            kwargs["timestamp"] = kwargs["timestamp"].isoformat()
        df, info = self.process_data(self.endpoints.analysis, kwargs, "single")
        return {"data": df, "exists": info["existance"], "id": info["id"], "response": info.get("response")}

    def list_results(self, **kwargs: Any) -> dict[str, Any]:
        """Return raw result rows from the backend.

        To return all the results related to a specific analysis, use on of the
        following:
        * `analysis` or `analysis__id` parameter with the analysis ID.
        * `analysis__name`, `analysis__model_definition__title`,
          `analysis__timestamp`, and `analysis__location__title` parameters
          because this identifies a single analysis (see `get_analysis`).

        Examples
        --------
        >>> from owi.metadatabase.results import ResultsAPI  # doctest: SKIP
        >>> api = ResultsAPI(token="dummy")  # doctest: SKIP
        >>> results = api.list_results(analysis__id=1)  # doctest: SKIP
        >>> results['exists']  # doctest: SKIP
        True  # doctest: SKIP
        """
        url_params = dict(kwargs)
        if "analysis" in url_params and "analysis__id" not in url_params:
            url_params["analysis__id"] = url_params.pop("analysis")
        df, info = self.process_data(self.endpoints.result, url_params, "list")
        return {"data": df, "exists": info["existance"], "response": info.get("response")}

    def get_results_raw(self, **kwargs: Any) -> dict[str, Any]:
        """Return a single raw result row."""
        df, info = self.process_data(self.endpoints.result, kwargs, "single")
        return {"data": df, "exists": info["existance"], "id": info["id"], "response": info.get("response")}

    def _auth_kwargs(self) -> dict[str, Any]:
        """Return authentication kwargs for auxiliary API clients."""
        if self.header is not None:
            return {"header": self.header}
        if self.uname is not None and self.password is not None:
            return {"uname": self.uname, "password": self.password}
        raise InvalidParameterError("Either header or username/password authentication must be configured.")

    def _authenticated_request(
        self,
        method: str,
        url: str,
        payload: Any,
    ) -> requests.Response:
        """Send an authenticated JSON request and validate the response status."""
        headers = {"Content-Type": "application/json"}
        if self.header is not None:
            headers.update(self.header)
            response = requests.request(method, url, headers=headers, json=payload)
        elif self.auth is not None:
            response = requests.request(method, url, auth=self.auth, headers=headers, json=payload)
        else:
            raise InvalidParameterError("Either header or username/password authentication must be configured.")
        if response.status_code not in {200, 201}:
            details = f"\n{response.text}" if response.text else ""
            message = f"Error {response.status_code}.\n{response.reason}{details}"
            raise APIConnectionError(message=message, response=response)
        return response

    def _send_json_request(self, endpoint: str, payload: Any, method: str = "post") -> requests.Response:
        """Send a JSON mutation request using the configured authentication."""
        url = self.api_root + self.endpoints.mutation_path(endpoint)
        return self._authenticated_request(method, url, payload)

    def _send_detail_json_request(
        self,
        endpoint: str,
        object_id: int,
        payload: Any,
        method: str = "patch",
    ) -> requests.Response:
        """Send a JSON mutation request to a detail endpoint."""
        url = self.api_root + self.endpoints.detail_path(endpoint, object_id)
        return self._authenticated_request(method, url, payload)

    @staticmethod
    def _response_to_dataframe(response: requests.Response) -> pd.DataFrame:
        """Convert a POST response body into a DataFrame."""
        payload = response.json()
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            return pd.DataFrame([payload])
        return pd.DataFrame()

    def _normalize_analysis_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Normalize analysis creation payloads to match backend expectations."""
        normalized = dict(payload)
        normalized.setdefault("location", None)
        if "model_definition" not in normalized and normalized.get("model_definition_id") is not None:
            normalized["model_definition"] = normalized["model_definition_id"]
        if "timestamp" in normalized and normalized["timestamp"] is not None:
            normalized["timestamp"] = normalized["timestamp"].isoformat()

        source = normalized.get("source")
        if isinstance(source, str):
            parsed = urlparse(source)
            if parsed.scheme not in {"http", "https"}:
                normalized["source"] = None

        return normalized

    def create_analysis(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Create a new analysis record."""
        response = self._send_json_request(
            self.endpoints.analysis,
            self._normalize_analysis_payload(payload),
            method="post",
        )
        df = self._response_to_dataframe(response)
        return {
            "data": df,
            "exists": not df.empty,
            "id": df["id"].iloc[0] if "id" in df and not df.empty else None,
            "response": response,
        }

    def create_result(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Create a single result row."""
        response = self._send_json_request(self.endpoints.result, dict(payload), method="post")
        df = self._response_to_dataframe(response)
        return {
            "data": df,
            "exists": not df.empty,
            "id": df["id"].iloc[0] if "id" in df and not df.empty else None,
            "response": response,
        }

    def update_result(self, result_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Patch a single result row."""
        response = self._send_detail_json_request(self.endpoints.result, result_id, dict(payload), method="patch")
        df = self._response_to_dataframe(response)
        return {
            "data": df,
            "exists": not df.empty,
            "id": df["id"].iloc[0] if "id" in df and not df.empty else result_id,
            "response": response,
        }

    def create_results_bulk(self, payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Create multiple result rows in one request.

        Falls back to single-row creation when the backend does not expose
        a bulk mutation endpoint.
        """
        serialized_payloads = [dict(payload) for payload in payloads]
        if not serialized_payloads:
            return {"data": pd.DataFrame(), "exists": False, "response": None}

        try:
            with tqdm(total=1, desc="Uploading result batch", unit="request") as progress:
                response = self._send_json_request(
                    self.endpoints.result_bulk,
                    serialized_payloads,
                    method="post",
                )
                progress.update(1)
            df = self._response_to_dataframe(response)
            return {"data": df, "exists": not df.empty, "response": response}
        except APIConnectionError as error:
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code not in {404, 405, 500}:
                raise

        rows = []
        with tqdm(total=len(serialized_payloads), desc="Uploading result rows", unit="row") as progress:
            for payload in serialized_payloads:
                rows.append(self.create_result(payload)["data"])
                progress.update(1)
        df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
        return {"data": df, "exists": not df.empty, "response": None}

    def create_or_update_results_bulk(self, payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Create missing result rows and patch existing ones in bulk.

        Existing rows are matched within the same analysis using the
        `short_description` field of each payload.

        If duplicate `short_description` values are found for the same result (row) in the backend,
        the method will raise an error to avoid ambiguity in the update process.
        In this case, the user should first resolve the duplicates in the backend, e.g. by
        renaming the `short_description` values, and then retry the bulk create or update operation.
        """
        serialized_payloads = [dict(payload) for payload in payloads]
        if not serialized_payloads:
            return {"data": pd.DataFrame(), "exists": False, "response": None, "summary": []}

        grouped_payloads: dict[int, list[dict[str, Any]]] = {}
        for payload in serialized_payloads:
            analysis_id = payload.get("analysis")
            short_description = payload.get("short_description")
            if analysis_id is None:
                raise InvalidParameterError("bulk create or update requires an `analysis` value for each payload.")
            if short_description is None:
                raise InvalidParameterError(
                    "bulk create or update requires a `short_description` value for each payload."
                )
            grouped_payloads.setdefault(int(analysis_id), []).append(payload)

        create_payloads: list[dict[str, Any]] = []
        update_requests: list[tuple[int, dict[str, Any]]] = []
        summary_by_key: dict[tuple[int, str], dict[str, Any]] = {}

        for analysis_id, analysis_payloads in grouped_payloads.items():
            existing_rows = self.list_results(analysis=analysis_id)["data"]
            existing_ids_by_description: dict[str, int] = {}

            if not existing_rows.empty and "short_description" in existing_rows.columns:
                requested_descriptions = [str(payload["short_description"]) for payload in analysis_payloads]
                relevant_rows = existing_rows.loc[
                    existing_rows["short_description"].astype(str).isin(requested_descriptions)
                ].copy()
                duplicate_counts = relevant_rows["short_description"].astype(str).value_counts()
                ambiguous_descriptions = duplicate_counts[duplicate_counts > 1]
                if not ambiguous_descriptions.empty:
                    duplicates = ", ".join(sorted(ambiguous_descriptions.index.tolist()))
                    raise InvalidParameterError(
                        "bulk create or update found multiple existing results for the same "
                        f"`short_description`: {duplicates}."
                    )

                existing_ids_by_description = {
                    str(row["short_description"]): int(row["id"])
                    for row in relevant_rows.to_dict(orient="records")
                    if row.get("id") is not None and row.get("short_description") is not None
                }

            for payload in analysis_payloads:
                identity = (analysis_id, str(payload["short_description"]))
                existing_id = existing_ids_by_description.get(identity[1])
                if existing_id is None:
                    create_payloads.append(payload)
                else:
                    update_requests.append((existing_id, payload))
                    summary_by_key[identity] = {
                        "analysis": analysis_id,
                        "short_description": identity[1],
                        "result_id": existing_id,
                        "action": "updated",
                    }

        frames: list[pd.DataFrame] = []
        if create_payloads:
            create_result = self.create_results_bulk(create_payloads)
            if not create_result["data"].empty:
                frames.append(create_result["data"])
            created_ids_by_key = {
                (int(row["analysis"]), str(row["short_description"])): int(row["id"])
                for row in create_result["data"].to_dict(orient="records")
                if row.get("id") is not None
                and row.get("analysis") is not None
                and row.get("short_description") is not None
            }
            for payload in create_payloads:
                identity = (int(payload["analysis"]), str(payload["short_description"]))
                summary_by_key[identity] = {
                    "analysis": identity[0],
                    "short_description": identity[1],
                    "result_id": created_ids_by_key.get(identity),
                    "action": "created",
                }

        if update_requests:
            with tqdm(total=len(update_requests), desc="Uploading existing result rows", unit="row") as progress:
                for result_id, payload in update_requests:
                    updated = self.update_result(result_id, payload)
                    if not updated["data"].empty:
                        frames.append(updated["data"])
                    progress.update(1)

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        summary = [
            summary_by_key[(int(payload["analysis"]), str(payload["short_description"]))]
            for payload in serialized_payloads
        ]
        return {"data": df, "exists": not df.empty, "response": None, "summary": summary}
