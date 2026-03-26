from unittest.mock import patch

import pandas as pd
import pytest
import requests
from owi.metadatabase._utils.exceptions import (  # ty: ignore[unresolved-import]
    APIConnectionError,
    InvalidParameterError,
)

from owi.metadatabase.results import DEFAULT_RESULTS_ENDPOINTS, ResultsAPI


class ProgressBarRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def factory(self, *args: object, **kwargs: object):
        updates: list[int] = []
        call: dict[str, object] = {"args": args, "kwargs": kwargs, "updates": updates}
        self.calls.append(call)

        class _ProgressBar:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb) -> bool:
                return False

            def update(self_inner, amount: int) -> None:
                updates.append(amount)

        return _ProgressBar()


def test_ping() -> None:
    api = ResultsAPI(token="dummy")
    assert api.ping() == "ok"


def test_default_base_url() -> None:
    api = ResultsAPI(token="dummy")
    assert api.api_root.startswith("https://")
    assert api.api_root.endswith("/results/routes/")


def test_base_api_root_preserved() -> None:
    api = ResultsAPI(token="dummy")
    assert not api.base_api_root.endswith("/results/routes/")


def test_list_analyses_calls_process_data() -> None:
    api = ResultsAPI(token="dummy")
    with patch.object(
        ResultsAPI, "process_data", return_value=(pd.DataFrame({"id": [1]}), {"existance": True})
    ) as mocker:
        result = api.list_analyses(name="WindSpeedHistogram")
    mocker.assert_called_once_with("analysis", {"name": "WindSpeedHistogram"}, "list")
    assert result["exists"] is True


def test_list_analyses_without_name() -> None:
    api = ResultsAPI(token="dummy")
    with patch.object(
        ResultsAPI, "process_data", return_value=(pd.DataFrame({"id": [1]}), {"existance": True})
    ) as mocker:
        api.list_analyses()
    mocker.assert_called_once_with("analysis", {}, "list")


def test_get_analysis_calls_process_data() -> None:
    api = ResultsAPI(token="dummy")
    with patch.object(
        ResultsAPI, "process_data", return_value=(pd.DataFrame({"id": [1]}), {"existance": True, "id": 1})
    ) as mocker:
        result = api.get_analysis(name="WindSpeedHistogram")
    mocker.assert_called_once_with("analysis", {"name": "WindSpeedHistogram"}, "single")
    assert result["id"] == 1


def test_list_results_calls_process_data() -> None:
    api = ResultsAPI(token="dummy")
    with patch.object(ResultsAPI, "process_data", return_value=(pd.DataFrame(), {"existance": False})) as mocker:
        result = api.list_results(analysis=5)
    mocker.assert_called_once_with("result", {"analysis__id": 5}, "list")
    assert result["exists"] is False


def test_get_results_raw_calls_process_data() -> None:
    api = ResultsAPI(token="dummy")
    with patch.object(
        ResultsAPI, "process_data", return_value=(pd.DataFrame({"id": [1]}), {"existance": True, "id": 1})
    ) as mocker:
        result = api.get_results_raw(id=1)
    mocker.assert_called_once_with("result", {"id": 1}, "single")
    assert result["id"] == 1


def test_create_analysis_posts_to_trailing_slash_endpoint() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 201
    response._content = b'{"id": 12, "name": "Example"}'
    response.reason = "Created"
    with patch("requests.request", return_value=response) as mocker:
        result = api.create_analysis(
            {"name": "Example", "model_definition_id": 4, "location_id": None, "source_type": "script"}
        )
    mocker.assert_called_once()
    assert mocker.call_args.args[1].endswith(DEFAULT_RESULTS_ENDPOINTS.mutation_path("analysis"))
    assert mocker.call_args.kwargs["json"]["model_definition_id"] == 4
    assert mocker.call_args.kwargs["json"]["model_definition"] == 4
    assert mocker.call_args.kwargs["json"]["location"] is None
    assert result["id"] == 12


def test_create_analysis_drops_local_source_and_sets_location_none() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 201
    response._content = b'{"id": 12, "name": "Example"}'
    response.reason = "Created"

    with patch("requests.request", return_value=response) as mocker:
        api.create_analysis(
            {
                "name": "Example",
                "model_definition_id": 4,
                "location_id": None,
                "source_type": "notebook",
                "source": "file:///tmp/example.ipynb",
            }
        )

    sent_payload = mocker.call_args.kwargs["json"]
    assert sent_payload["location"] is None
    assert sent_payload["model_definition_id"] == 4
    assert sent_payload["model_definition"] == 4
    assert sent_payload["source"] is None


def test_create_results_bulk_posts_to_bulk_endpoint() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 201
    response._content = b'[{"id": 1}, {"id": 2}]'
    response.reason = "Created"
    payloads = [{"analysis": 1, "name_col1": "x"}, {"analysis": 1, "name_col1": "y"}]
    with patch("requests.request", return_value=response) as mocker:
        result = api.create_results_bulk(payloads)
    mocker.assert_called_once()
    assert mocker.call_args.args[1].endswith(DEFAULT_RESULTS_ENDPOINTS.mutation_path("result/bulk"))
    assert result["exists"] is True


def test_create_results_bulk_uses_batch_progress_bar() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 201
    response._content = b'[{"id": 1}, {"id": 2}]'
    response.reason = "Created"
    payloads = [{"analysis": 1, "name_col1": "x"}, {"analysis": 1, "name_col1": "y"}]
    progress = ProgressBarRecorder()

    with (
        patch("owi.metadatabase.results.io.tqdm", new=progress.factory),
        patch("requests.request", return_value=response),
    ):
        api.create_results_bulk(payloads)

    assert len(progress.calls) == 1
    kwargs = progress.calls[0]["kwargs"]
    assert kwargs == {
        "total": 1,
        "desc": "Uploading result batch",
        "unit": "request",
    }
    assert progress.calls[0]["updates"] == [1]


def test_create_results_bulk_falls_back_to_single_posts_when_bulk_is_not_supported() -> None:
    api = ResultsAPI(token="dummy")

    bulk_response = requests.Response()
    bulk_response.status_code = 405
    bulk_response.reason = "Method Not Allowed"
    bulk_response._content = b""

    first_result = requests.Response()
    first_result.status_code = 201
    first_result.reason = "Created"
    first_result._content = b'{"id": 1, "analysis": 10, "name_col1": "x"}'

    second_result = requests.Response()
    second_result.status_code = 201
    second_result.reason = "Created"
    second_result._content = b'{"id": 2, "analysis": 10, "name_col1": "y"}'

    payloads = [{"analysis": 10, "name_col1": "x"}, {"analysis": 10, "name_col1": "y"}]
    with patch("requests.request", side_effect=[bulk_response, first_result, second_result]) as mocker:
        result = api.create_results_bulk(payloads)

    assert mocker.call_count == 3
    assert mocker.call_args_list[0].args[1].endswith(DEFAULT_RESULTS_ENDPOINTS.mutation_path("result/bulk"))
    assert mocker.call_args_list[1].args[1].endswith(DEFAULT_RESULTS_ENDPOINTS.mutation_path("result"))
    assert mocker.call_args_list[2].args[1].endswith(DEFAULT_RESULTS_ENDPOINTS.mutation_path("result"))
    assert result["exists"] is True
    assert list(result["data"]["id"]) == [1, 2]


def test_create_results_bulk_fallback_uses_row_progress_bar() -> None:
    api = ResultsAPI(token="dummy")

    bulk_response = requests.Response()
    bulk_response.status_code = 405
    bulk_response.reason = "Method Not Allowed"
    bulk_response._content = b""

    first_result = requests.Response()
    first_result.status_code = 201
    first_result.reason = "Created"
    first_result._content = b'{"id": 1, "analysis": 10, "name_col1": "x"}'

    second_result = requests.Response()
    second_result.status_code = 201
    second_result.reason = "Created"
    second_result._content = b'{"id": 2, "analysis": 10, "name_col1": "y"}'

    progress = ProgressBarRecorder()
    payloads = [{"analysis": 10, "name_col1": "x"}, {"analysis": 10, "name_col1": "y"}]

    with (
        patch("owi.metadatabase.results.io.tqdm", new=progress.factory),
        patch("requests.request", side_effect=[bulk_response, first_result, second_result]),
    ):
        api.create_results_bulk(payloads)

    assert len(progress.calls) == 2
    assert progress.calls[0]["kwargs"] == {
        "total": 1,
        "desc": "Uploading result batch",
        "unit": "request",
    }
    assert progress.calls[0]["updates"] == []
    assert progress.calls[1]["kwargs"] == {
        "total": 2,
        "desc": "Uploading result rows",
        "unit": "row",
    }
    assert progress.calls[1]["updates"] == [1, 1]


def test_create_results_bulk_falls_back_on_404() -> None:
    api = ResultsAPI(token="dummy")

    bulk_response = requests.Response()
    bulk_response.status_code = 404
    bulk_response.reason = "Not Found"
    bulk_response._content = b""

    single_response = requests.Response()
    single_response.status_code = 201
    single_response.reason = "Created"
    single_response._content = b'{"id": 1}'

    with patch("requests.request", side_effect=[bulk_response, single_response]):
        result = api.create_results_bulk([{"analysis": 1}])
    assert result["exists"] is True


def test_create_results_bulk_raises_on_server_error() -> None:
    api = ResultsAPI(token="dummy")

    bulk_response = requests.Response()
    bulk_response.status_code = 502
    bulk_response.reason = "Bad Gateway"
    bulk_response._content = b""

    with patch("requests.request", return_value=bulk_response), pytest.raises(APIConnectionError):
        api.create_results_bulk([{"analysis": 1}])


def test_create_results_bulk_falls_back_on_500() -> None:
    api = ResultsAPI(token="dummy")

    bulk_response = requests.Response()
    bulk_response.status_code = 500
    bulk_response.reason = "Internal Server Error"
    bulk_response._content = b""

    single_response = requests.Response()
    single_response.status_code = 201
    single_response.reason = "Created"
    single_response._content = b'{"id": 1}'

    with patch("requests.request", side_effect=[bulk_response, single_response]):
        result = api.create_results_bulk([{"analysis": 1}])

    assert result["exists"] is True


def test_update_result_patches_detail_endpoint() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 200
    response.reason = "OK"
    response._content = b'{"id": 7, "analysis": 10, "name_col1": "timestamp"}'
    with patch("requests.request", return_value=response) as mocker:
        result = api.update_result(7, {"analysis": 10, "name_col1": "timestamp"})
    mocker.assert_called_once()
    assert mocker.call_args.args[1].endswith(DEFAULT_RESULTS_ENDPOINTS.detail_path("result", 7))
    assert result["id"] == 7


def test_send_json_request_raises_without_auth() -> None:
    api = ResultsAPI.__new__(ResultsAPI)
    api.header = None
    api.auth = None
    api.api_root = "https://example.com"
    api.endpoints = DEFAULT_RESULTS_ENDPOINTS
    with pytest.raises(InvalidParameterError):
        api._send_json_request("analysis", {"name": "test"})


def test_send_detail_json_request_raises_without_auth() -> None:
    api = ResultsAPI.__new__(ResultsAPI)
    api.header = None
    api.auth = None
    api.api_root = "https://example.com"
    api.endpoints = DEFAULT_RESULTS_ENDPOINTS
    with pytest.raises(InvalidParameterError):
        api._send_detail_json_request("result", 1, {"name": "test"})


def test_send_json_request_raises_on_bad_status() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 400
    response.reason = "Bad Request"
    response._content = b""
    with patch("requests.request", return_value=response), pytest.raises(APIConnectionError):
        api._send_json_request("analysis", {"name": "test"})


def test_send_detail_json_request_raises_on_bad_status() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 403
    response.reason = "Forbidden"
    response._content = b""
    with patch("requests.request", return_value=response), pytest.raises(APIConnectionError):
        api._send_detail_json_request("result", 1, {"name": "test"})


def test_response_to_dataframe_list() -> None:
    response = requests.Response()
    response.status_code = 200
    response._content = b'[{"id": 1}, {"id": 2}]'
    df = ResultsAPI._response_to_dataframe(response)
    assert list(df["id"]) == [1, 2]


def test_response_to_dataframe_dict() -> None:
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"id": 1}'
    df = ResultsAPI._response_to_dataframe(response)
    assert list(df["id"]) == [1]


def test_response_to_dataframe_other() -> None:
    response = requests.Response()
    response.status_code = 200
    response._content = b'"just a string"'
    df = ResultsAPI._response_to_dataframe(response)
    assert df.empty


def test_auth_kwargs_with_header() -> None:
    api = ResultsAPI(token="dummy")
    kwargs = api._auth_kwargs()
    assert "header" in kwargs


def test_auth_kwargs_with_uname_password() -> None:
    api = ResultsAPI(uname="user", password="pass")
    kwargs = api._auth_kwargs()
    assert "uname" in kwargs
    assert "password" in kwargs


def test_auth_kwargs_raises_without_auth() -> None:
    api = ResultsAPI.__new__(ResultsAPI)
    api.header = None
    api.uname = None
    api.password = None
    with pytest.raises(InvalidParameterError):
        api._auth_kwargs()


def test_send_json_request_with_basic_auth() -> None:
    api = ResultsAPI(uname="user", password="pass")
    response = requests.Response()
    response.status_code = 201
    response._content = b'{"id": 1}'
    response.reason = "Created"
    with patch("requests.request", return_value=response) as mocker:
        api._send_json_request("analysis", {"name": "test"})
    assert mocker.call_args.kwargs.get("auth") is not None


def test_send_detail_json_request_with_basic_auth() -> None:
    api = ResultsAPI(uname="user", password="pass")
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"id": 1}'
    response.reason = "OK"
    with patch("requests.request", return_value=response) as mocker:
        api._send_detail_json_request("result", 1, {"name": "test"})
    assert mocker.call_args.kwargs.get("auth") is not None


def test_create_result_returns_id() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 201
    response._content = b'{"id": 99}'
    response.reason = "Created"
    with patch("requests.request", return_value=response):
        result = api.create_result({"analysis": 1, "name_col1": "x"})
    assert result["id"] == 99
    assert result["exists"] is True
