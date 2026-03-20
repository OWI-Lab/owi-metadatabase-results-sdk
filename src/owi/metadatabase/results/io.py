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

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
import requests
from owi.metadatabase._utils.exceptions import (  # ty: ignore[unresolved-import]
    APIConnectionError,
    InvalidParameterError,
)
from owi.metadatabase.io import API  # ty: ignore[unresolved-import]
from owi.metadatabase.locations.io import LocationsAPI  # ty: ignore[unresolved-import]

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
        """Return a single analysis row."""
        df, info = self.process_data(self.endpoints.analysis, kwargs, "single")
        return {"data": df, "exists": info["existance"], "id": info["id"], "response": info.get("response")}

    def list_results(self, **kwargs: Any) -> dict[str, Any]:
        """Return raw result rows from the backend."""
        df, info = self.process_data(self.endpoints.result, kwargs, "list")
        return {"data": df, "exists": info["existance"], "response": info.get("response")}

    def get_results_raw(self, **kwargs: Any) -> dict[str, Any]:
        """Return a single raw result row."""
        df, info = self.process_data(self.endpoints.result, kwargs, "single")
        return {"data": df, "exists": info["existance"], "id": info["id"], "response": info.get("response")}

    def _send_json_request(self, endpoint: str, payload: Any, method: str = "post") -> requests.Response:
        """Send a JSON mutation request using the configured authentication."""
        headers = {"Content-Type": "application/json"}
        url = self.api_root + self.endpoints.mutation_path(endpoint)
        if self.header is not None:
            headers.update(self.header)
            response = requests.request(method, url, headers=headers, json=payload)
        elif self.auth is not None:
            response = requests.request(method, url, auth=self.auth, headers=headers, json=payload)
        else:
            raise InvalidParameterError("Either header or username/password authentication must be configured.")
        if response.status_code not in {200, 201}:
            raise APIConnectionError(message=f"Error {response.status_code}.\n{response.reason}", response=response)
        return response

    def _send_detail_json_request(
        self,
        endpoint: str,
        object_id: int,
        payload: Any,
        method: str = "patch",
    ) -> requests.Response:
        """Send a JSON mutation request to a detail endpoint."""
        headers = {"Content-Type": "application/json"}
        url = self.api_root + self.endpoints.detail_path(endpoint, object_id)
        if self.header is not None:
            headers.update(self.header)
            response = requests.request(method, url, headers=headers, json=payload)
        elif self.auth is not None:
            response = requests.request(method, url, auth=self.auth, headers=headers, json=payload)
        else:
            raise InvalidParameterError("Either header or username/password authentication must be configured.")
        if response.status_code not in {200, 201}:
            raise APIConnectionError(message=f"Error {response.status_code}.\n{response.reason}", response=response)
        return response

    @staticmethod
    def _response_to_dataframe(response: requests.Response) -> pd.DataFrame:
        """Convert a POST response body into a DataFrame."""
        payload = response.json()
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            return pd.DataFrame([payload])
        return pd.DataFrame()

    def create_analysis(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Create a new analysis record."""
        response = self._send_json_request(self.endpoints.analysis, dict(payload), method="post")
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
        try:
            response = self._send_json_request(
                self.endpoints.result_bulk,
                serialized_payloads,
                method="post",
            )
            df = self._response_to_dataframe(response)
            return {"data": df, "exists": not df.empty, "response": response}
        except APIConnectionError as error:
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code not in {404, 405}:
                raise

        rows = [self.create_result(payload)["data"] for payload in serialized_payloads]
        df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
        return {"data": df, "exists": not df.empty, "response": None}

    def get_analyses(self, name: str | None = None) -> dict[str, Any]:
        """Backward-compatible wrapper for list_analyses."""
        return self.list_analyses(name=name)

    def _auth_kwargs(self) -> dict[str, Any]:
        """Return authentication kwargs for auxiliary API clients."""
        if self.header is not None:
            return {"header": self.header}
        if self.uname is not None and self.password is not None:
            return {"uname": self.uname, "password": self.password}
        raise InvalidParameterError("Either header or username/password authentication must be configured.")

    @staticmethod
    def _empty_list_response() -> dict[str, Any]:
        """Return an empty list-style response payload."""
        return {"data": pd.DataFrame(), "exists": False, "response": None}

    def get_results(
        self,
        assetlocation: str | None = None,
        projectsite: str | None = None,
        analysis: str | int | None = None,
        short_description: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Backward-compatible wrapper for list_results with friendly filters."""
        url_params = dict(kwargs)
        location_api = LocationsAPI(api_root=self.base_api_root, **self._auth_kwargs())

        if projectsite is not None:
            site_response = location_api.get_projectsite_detail(projectsite=projectsite)
            if not site_response["exists"] or site_response["id"] is None:
                return self._empty_list_response()
            url_params["site"] = int(site_response["id"])
        if assetlocation is not None:
            location_response = location_api.get_assetlocation_detail(assetlocation=assetlocation, projectsite=projectsite)
            if not location_response["exists"] or location_response["id"] is None:
                return self._empty_list_response()
            url_params["location"] = int(location_response["id"])
        if short_description is not None:
            url_params["short_description"] = short_description

        if analysis is None:
            return self.list_results(**url_params)

        if isinstance(analysis, int):
            return self.list_results(analysis=analysis, **url_params)

        analysis_frame = self.list_analyses(name=analysis)["data"]
        if analysis_frame.empty or "id" not in analysis_frame:
            return self._empty_list_response()

        analysis_ids = analysis_frame["id"].dropna().astype(int).tolist()
        if not analysis_ids:
            return self._empty_list_response()

        frames = [self.list_results(analysis=analysis_id, **url_params)["data"] for analysis_id in analysis_ids]
        data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return {"data": data, "exists": not data.empty, "response": None}
