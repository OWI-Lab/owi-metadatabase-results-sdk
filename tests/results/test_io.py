from unittest.mock import patch

import pandas as pd
import requests

from owi.metadatabase.results import DEFAULT_RESULTS_ENDPOINTS, ResultsAPI


def test_ping() -> None:
    api = ResultsAPI(token="dummy")
    assert api.ping() == "ok"


def test_default_base_url() -> None:
    api = ResultsAPI(token="dummy")
    assert api.api_root.startswith("https://")
    assert api.api_root.endswith("/results/routes/")


def test_list_analyses_calls_process_data() -> None:
    api = ResultsAPI(token="dummy")
    with patch.object(
        ResultsAPI, "process_data", return_value=(pd.DataFrame({"id": [1]}), {"existance": True})
    ) as mocker:
        result = api.list_analyses(name="WindSpeedHistogram")
    mocker.assert_called_once_with("analysis", {"name": "WindSpeedHistogram"}, "list")
    assert result["exists"] is True


def test_get_results_backwards_compatible_filters() -> None:
    api = ResultsAPI(token="dummy")
    with (
        patch("owi.metadatabase.results.io.LocationsAPI.get_projectsite_detail", return_value={"id": 9, "exists": True}),
        patch(
            "owi.metadatabase.results.io.LocationsAPI.get_assetlocation_detail",
            return_value={"id": 11, "exists": True},
        ),
        patch.object(ResultsAPI, "list_analyses", return_value={"data": pd.DataFrame({"id": [5]})}),
        patch.object(ResultsAPI, "list_results", return_value={"data": pd.DataFrame(), "exists": False}) as mocker,
    ):
        api.get_results(assetlocation="WTG1", projectsite="SiteA", analysis="WindSpeedHistogram")
    mocker.assert_called_once_with(
        analysis=5,
        location=11,
        site=9,
    )


def test_get_results_returns_empty_when_projectsite_cannot_be_resolved() -> None:
    api = ResultsAPI(token="dummy")
    with patch(
        "owi.metadatabase.results.io.LocationsAPI.get_projectsite_detail",
        return_value={"id": None, "exists": False},
    ):
        result = api.get_results(projectsite="non-existing-project")
    assert result["exists"] is False
    assert result["data"].empty


def test_get_results_combines_matching_analysis_ids() -> None:
    api = ResultsAPI(token="dummy")
    with (
        patch.object(ResultsAPI, "list_analyses", return_value={"data": pd.DataFrame({"id": [5, 6]})}),
        patch.object(
            ResultsAPI,
            "list_results",
            side_effect=[
                {"data": pd.DataFrame({"analysis": [5], "value": [1.0]}), "exists": True},
                {"data": pd.DataFrame({"analysis": [6], "value": [2.0]}), "exists": True},
            ],
        ) as mocker,
    ):
        result = api.get_results(analysis="WindSpeedHistogram")

    assert mocker.call_args_list[0].kwargs == {"analysis": 5}
    assert mocker.call_args_list[1].kwargs == {"analysis": 6}
    assert list(result["data"]["analysis"]) == [5, 6]


def test_create_analysis_posts_to_trailing_slash_endpoint() -> None:
    api = ResultsAPI(token="dummy")
    response = requests.Response()
    response.status_code = 201
    response._content = b'{"id": 12, "name": "Example"}'
    response.reason = "Created"
    with patch("requests.request", return_value=response) as mocker:
        result = api.create_analysis({"name": "Example", "source_type": "script"})
    mocker.assert_called_once()
    assert mocker.call_args.args[1].endswith(DEFAULT_RESULTS_ENDPOINTS.mutation_path("analysis"))
    assert result["id"] == 12


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
