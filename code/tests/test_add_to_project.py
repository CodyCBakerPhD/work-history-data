import json
import os
import pathlib
import time
import unittest.mock
import warnings as _warnings_module

import pytest
import requests

import my_work_history
from my_work_history._add_to_project import (
    _add_item_to_project,
    _check_graphql_response,
    _collect_unique_urls,
    _get_item_info,
    _get_project_info,
    _list_project_item_content_urls,
    _list_project_items_with_dates,
    _set_item_date,
    _set_item_status,
    update_project_item_dates,
)

# ---------------------------------------------------------------------------
# Helpers shared across integration tests
# ---------------------------------------------------------------------------

_TEST_PROJECT_URL = "https://github.com/users/CodyCBakerPhD/projects/5"
# A known closed PR in the repository – used as the integration-test fixture URL.
_KNOWN_CLOSED_PR_URL = "https://github.com/CodyCBakerPhD/work-history-data/pull/1"


def _has_valid_github_token() -> bool:
    token = os.getenv("GITHUB_TOKEN", "")
    return bool(token) and not token.startswith("fake")


def _make_headers() -> dict[str, str]:
    return {"Authorization": f"token {os.environ['GITHUB_TOKEN']}"}


def _list_project_items_with_urls(headers: dict[str, str]) -> dict[str, str]:
    """Return a mapping of {content_url: item_id} for ALL items in the test project.

    Uses cursor-based pagination to retrieve items beyond the first page.
    """
    query = """
query($login: String!, $number: Int!, $after: String) {
    user(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    content {
                        ... on PullRequest { url }
                        ... on Issue { url }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    }
}
"""
    all_items: dict[str, str] = {}
    after_cursor = None

    while True:
        variables: dict = {"login": "CodyCBakerPhD", "number": 5, "after": after_cursor}
        response = requests.post(
            url="https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
        )
        if response.status_code == 403:
            raise PermissionError("GitHub token lacks project permissions (403)")
        result = response.json()
        items_data = result["data"]["user"]["projectV2"]["items"]
        for node in items_data["nodes"]:
            if node.get("content") and node["content"].get("url"):
                all_items[node["content"]["url"]] = node["id"]
        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return all_items


def _delete_project_item(project_id: str, item_id: str, headers: dict[str, str]) -> None:
    """Delete a single item from the test project."""
    mutation = """
mutation($projectId: ID!, $itemId: ID!) {
    deleteProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
        deletedItemId
    }
}
"""
    requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": {"projectId": project_id, "itemId": item_id}},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Unit tests – no network calls
# ---------------------------------------------------------------------------


def test_add_to_project_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        my_work_history.add_to_project(
            directory=pathlib.Path("/tmp/nonexistent"),
            project_url=_TEST_PROJECT_URL,
        )


def test_add_to_project_warns_when_no_urls(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    with pytest.warns(UserWarning, match="No URLs found"):
        my_work_history.add_to_project(directory=tmp_path, project_url=_TEST_PROJECT_URL)


def test_collect_unique_urls_reads_json_files(tmp_path: pathlib.Path) -> None:
    urls_a = ["https://github.com/owner/repo/pull/1", "https://github.com/owner/repo/pull/2"]
    urls_b = ["https://github.com/owner/repo/pull/2", "https://github.com/owner/repo/issues/3"]

    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.json").write_text(json.dumps(urls_a))
    (sub / "b.json").write_text(json.dumps(urls_b))

    result = _collect_unique_urls(directory=tmp_path)

    assert set(result) == {
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/pull/2",
        "https://github.com/owner/repo/issues/3",
    }


def test_collect_unique_urls_handles_rest_format(tmp_path: pathlib.Path) -> None:
    """REST API response dicts should have html_url extracted from items, not dict keys."""
    rest_response = {
        "total_count": 2,
        "incomplete_results": False,
        "search_type": "lexical",
        "items": [
            {"html_url": "https://github.com/owner/repo/pull/10", "other_field": "ignored"},
            {"html_url": "https://github.com/owner/repo/issues/20", "other_field": "ignored"},
        ],
    }
    (tmp_path / "rest.json").write_text(json.dumps(rest_response))

    result = _collect_unique_urls(directory=tmp_path)

    assert set(result) == {
        "https://github.com/owner/repo/pull/10",
        "https://github.com/owner/repo/issues/20",
    }


def test_collect_unique_urls_mixed_formats(tmp_path: pathlib.Path) -> None:
    """A directory with both REST and GraphQL JSON files should collect all URLs correctly."""
    graphql_urls = ["https://github.com/owner/repo/pull/1"]
    rest_response = {
        "total_count": 1,
        "incomplete_results": False,
        "search_type": "lexical",
        "items": [{"html_url": "https://github.com/owner/repo/issues/2"}],
    }
    (tmp_path / "graphql.json").write_text(json.dumps(graphql_urls))
    (tmp_path / "rest.json").write_text(json.dumps(rest_response))

    result = _collect_unique_urls(directory=tmp_path)

    assert set(result) == {
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/issues/2",
    }


def test_check_graphql_response_returns_result_on_success() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"foo": "bar"}}

    result = _check_graphql_response(response=mock_response, context="test")

    assert result == {"data": {"foo": "bar"}}


def test_check_graphql_response_warns_on_403() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "Forbidden"}

    with pytest.warns(UserWarning):
        with pytest.raises(RuntimeError):
            _check_graphql_response(response=mock_response, context="test 403")


def test_check_graphql_response_raises_on_errors_key() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "some error"}]}

    with pytest.raises(RuntimeError):
        _check_graphql_response(response=mock_response, context="test errors")


def test_get_project_info_parses_user_url() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOA",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_id",
                                "name": "Status",
                                "options": [
                                    {"id": "opt1", "name": "Todo"},
                                    {"id": "opt2", "name": "In Progress"},
                                    {"id": "opt3", "name": "Done"},
                                ],
                            },
                            {"id": "PVTF_start", "name": "Start date", "dataType": "DATE"},
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ]
                    },
                }
            }
        }
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        project_id, status_field_id, status_options, start_date_field_id, end_date_field_id = _get_project_info(
            project_url="https://github.com/users/testuser/projects/1",
            headers=headers,
        )

    assert project_id == "PVT_kwDOA"
    assert status_field_id == "PVTSSF_id"
    assert status_options == {"Todo": "opt1", "In Progress": "opt2", "Done": "opt3"}
    assert start_date_field_id == "PVTF_start"
    assert end_date_field_id == "PVTF_end"


def test_get_project_info_returns_none_for_missing_date_fields() -> None:
    """When the project has no Start date / End date fields, their IDs are None."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOA",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_id",
                                "name": "Status",
                                "options": [{"id": "opt1", "name": "Todo"}],
                            }
                        ]
                    },
                }
            }
        }
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        _, _, _, start_date_field_id, end_date_field_id = _get_project_info(
            project_url="https://github.com/users/testuser/projects/1",
            headers=headers,
        )


def test_get_project_info_raises_when_no_status_field() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOA",
                    "fields": {"nodes": []},
                }
            }
        }
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        with pytest.raises(ValueError, match="No 'Status' field"):
            _get_project_info(
                project_url="https://github.com/users/testuser/projects/1",
                headers=headers,
            )


def test_get_item_info_returns_none_when_resource_is_null() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"resource": None}}

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        result = _get_item_info(url="https://github.com/owner/repo/pull/999", headers=headers)

    assert result is None


def test_get_item_info_classifies_pull_request() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "CLOSED",
                "createdAt": "2023-01-10T12:00:00Z",
                "closedAt": "2023-02-01T09:00:00Z",
            }
        }
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        node_id, item_type, item_state, created_at, closed_at = _get_item_info(
            url="https://github.com/owner/repo/pull/1", headers=headers
        )

    assert node_id == "PR_node_id"
    assert item_type == "PullRequest"
    assert item_state == "closed"
    assert created_at == "2023-01-10T12:00:00Z"
    assert closed_at == "2023-02-01T09:00:00Z"


def test_get_item_info_classifies_issue() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "resource": {
                "id": "ISSUE_node_id",
                "state": "OPEN",
                "createdAt": "2023-03-05T08:00:00Z",
                "closedAt": None,
            }
        }
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        node_id, item_type, item_state, created_at, closed_at = _get_item_info(
            url="https://github.com/owner/repo/issues/5", headers=headers
        )

    assert node_id == "ISSUE_node_id"
    assert item_type == "Issue"
    assert item_state == "open"
    assert created_at == "2023-03-05T08:00:00Z"
    assert closed_at is None


def test_add_item_to_project_returns_item_id() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"addProjectV2ItemById": {"item": {"id": "PVTI_item_id"}}}
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        item_id = _add_item_to_project(
            project_id="PVT_kwDOA", content_id="PR_node_id", headers=headers
        )

    assert item_id == "PVTI_item_id"


def test_add_item_to_project_returns_none_on_403() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "Forbidden"}

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        with pytest.warns(UserWarning):
            item_id = _add_item_to_project(
                project_id="PVT_kwDOA", content_id="PR_node_id", headers=headers
            )

    assert item_id is None


def test_set_item_status_calls_mutation() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_item_id"}}}
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _set_item_status(
            project_id="PVT_kwDOA",
            item_id="PVTI_item_id",
            field_id="PVTSSF_id",
            option_id="opt_done",
            headers=headers,
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    variables = call_kwargs["json"]["variables"]
    assert variables["projectId"] == "PVT_kwDOA"
    assert variables["itemId"] == "PVTI_item_id"
    assert variables["fieldId"] == "PVTSSF_id"
    assert variables["optionId"] == "opt_done"


def test_add_to_project_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Full flow test using mocked HTTP calls."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    pr_url = "https://github.com/owner/repo/pull/1"
    (tmp_path / "urls.json").write_text(json.dumps([pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [
                                    {"id": "opt_done", "name": "Done"},
                                    {"id": "opt_progress", "name": "In Progress"},
                                    {"id": "opt_todo", "name": "Todo"},
                                ],
                            }
                        ]
                    },
                }
            }
        }
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "CLOSED",
                "createdAt": "2023-01-10T12:00:00Z",
                "closedAt": "2023-02-01T09:00:00Z",
            }
        }
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {
        "data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}
    }

    set_status_response = unittest.mock.MagicMock()
    set_status_response.status_code = 200
    set_status_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}}
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    response_sequence = [project_info_response, empty_project_response, item_info_response, add_item_response, set_status_response]

    with unittest.mock.patch("requests.post", side_effect=response_sequence):
        my_work_history.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
        )


def test_add_to_project_skips_url_with_null_resource(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Items that return a null resource are silently skipped."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    (tmp_path / "urls.json").write_text(json.dumps(["https://github.com/owner/repo/pull/999"]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            }
                        ]
                    },
                }
            }
        }
    }

    null_resource_response = unittest.mock.MagicMock()
    null_resource_response.status_code = 200
    null_resource_response.json.return_value = {"data": {"resource": None}}

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    with unittest.mock.patch(
        "requests.post", side_effect=[project_info_response, empty_project_response, null_resource_response]
    ):
        with _warnings_module.catch_warnings():
            _warnings_module.simplefilter("error")
            my_work_history.add_to_project(
                directory=tmp_path,
                project_url="https://github.com/users/testuser/projects/1",
            )


def test_add_to_project_status_override(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """When a custom status is provided, all items receive that status regardless of their type/state."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    # Use an open issue URL – without override it would get 'Todo', with override it should get 'In Progress'.
    issue_url = "https://github.com/owner/repo/issues/10"
    (tmp_path / "urls.json").write_text(json.dumps([issue_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [
                                    {"id": "opt_done", "name": "Done"},
                                    {"id": "opt_progress", "name": "In Progress"},
                                    {"id": "opt_todo", "name": "Todo"},
                                ],
                            }
                        ]
                    },
                }
            }
        }
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "ISSUE_node_id",
                "state": "OPEN",
                "createdAt": "2023-03-05T08:00:00Z",
                "closedAt": None,
            }
        }
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {
        "data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}
    }

    set_status_response = unittest.mock.MagicMock()
    set_status_response.status_code = 200
    set_status_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}}
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    response_sequence = [project_info_response, empty_project_response, item_info_response, add_item_response, set_status_response]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        my_work_history.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            status="In Progress",
        )

    # The last call should be the set_status mutation; verify the option ID corresponds to 'In Progress'.
    set_status_call = mock_post.call_args_list[-1]
    variables = set_status_call.kwargs["json"]["variables"]
    assert variables["optionId"] == "opt_progress"


def test_add_to_project_status_override_unknown_status_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """When the overriding status value is not found in the project, a warning is emitted."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    pr_url = "https://github.com/owner/repo/pull/1"
    (tmp_path / "urls.json").write_text(json.dumps([pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            }
                        ]
                    },
                }
            }
        }
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "OPEN",
                "createdAt": "2023-04-01T10:00:00Z",
                "closedAt": None,
            }
        }
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {
        "data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    response_sequence = [project_info_response, empty_project_response, item_info_response, add_item_response]

    with unittest.mock.patch("requests.post", side_effect=response_sequence):
        with pytest.warns(UserWarning, match="not found in project"):
            my_work_history.add_to_project(
                directory=tmp_path,
                project_url="https://github.com/users/testuser/projects/1",
                status="NonExistentStatus",
            )


def test_set_item_date_calls_mutation() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_item_id"}}}
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _set_item_date(
            project_id="PVT_kwDOA",
            item_id="PVTI_item_id",
            field_id="PVTF_date",
            date="2023-01-15",
            headers=headers,
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    variables = call_kwargs["json"]["variables"]
    assert variables["projectId"] == "PVT_kwDOA"
    assert variables["itemId"] == "PVTI_item_id"
    assert variables["fieldId"] == "PVTF_date"
    assert variables["date"] == "2023-01-15"


def test_add_to_project_sets_dates_when_fields_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """When the project has Start date / End date fields, they are set on added items."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    pr_url = "https://github.com/owner/repo/pull/1"
    (tmp_path / "urls.json").write_text(json.dumps([pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_start", "name": "Start date", "dataType": "DATE"},
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ]
                    },
                }
            }
        }
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "CLOSED",
                "createdAt": "2023-01-10T12:00:00Z",
                "closedAt": "2023-02-01T09:00:00Z",
            }
        }
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {
        "data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}
    }

    set_field_response = unittest.mock.MagicMock()
    set_field_response.status_code = 200
    set_field_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}}
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    # project_info, list_project_item_content_urls, item_info, add_item, set_status, set_start_date, set_end_date
    response_sequence = [
        project_info_response,
        empty_project_response,
        item_info_response,
        add_item_response,
        set_field_response,  # set_status
        set_field_response,  # set_start_date
        set_field_response,  # set_end_date
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        my_work_history.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
        )

    # 7 calls total: project_info, list_project_item_content_urls, item_info, add_item, set_status, set_start_date, set_end_date
    assert mock_post.call_count == 7
    # Check start date call (6th call, index 5)
    start_date_call = mock_post.call_args_list[5]
    start_vars = start_date_call.kwargs["json"]["variables"]
    assert start_vars["fieldId"] == "PVTF_start"
    assert start_vars["date"] == "2023-01-10"
    # Check end date call (7th call, index 6)
    end_date_call = mock_post.call_args_list[6]
    end_vars = end_date_call.kwargs["json"]["variables"]
    assert end_vars["fieldId"] == "PVTF_end"
    assert end_vars["date"] == "2023-02-01"


def test_add_to_project_uses_placeholder_end_date_for_open_item(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """For open items, the end date is set to creation date + end_date_placeholder_days."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    issue_url = "https://github.com/owner/repo/issues/5"
    (tmp_path / "urls.json").write_text(json.dumps([issue_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_todo", "name": "Todo"}],
                            },
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ]
                    },
                }
            }
        }
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "ISSUE_node_id",
                "state": "OPEN",
                "createdAt": "2023-06-01T00:00:00Z",
                "closedAt": None,
            }
        }
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {
        "data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}
    }

    set_field_response = unittest.mock.MagicMock()
    set_field_response.status_code = 200
    set_field_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}}
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    response_sequence = [
        project_info_response,
        empty_project_response,
        item_info_response,
        add_item_response,
        set_field_response,  # set_status
        set_field_response,  # set_end_date (no start date field in this project)
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        my_work_history.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            end_date_placeholder_days=30,
        )

    # Check end date uses the placeholder (2023-06-01 + 30 days = 2023-07-01)
    end_date_call = mock_post.call_args_list[-1]
    end_vars = end_date_call.kwargs["json"]["variables"]
    assert end_vars["fieldId"] == "PVTF_end"
    assert end_vars["date"] == "2023-07-01"


def test_update_project_item_dates_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        update_project_item_dates(project_url="https://github.com/users/testuser/projects/1")


def test_update_project_item_dates_warns_when_no_date_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the project has no Start date / End date fields, a warning is emitted and no updates are made."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            }
                        ]
                    },
                }
            }
        }
    }

    with unittest.mock.patch("requests.post", return_value=project_info_response):
        with pytest.warns(UserWarning, match="no 'Start date' or 'End date' fields"):
            update_project_item_dates(project_url="https://github.com/users/testuser/projects/1")


def test_update_project_item_dates_updates_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """update_project_item_dates sets dates on all items already in the project."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_start", "name": "Start date", "dataType": "DATE"},
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ]
                    },
                }
            }
        }
    }

    list_items_response = unittest.mock.MagicMock()
    list_items_response.status_code = 200
    list_items_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_closed",
                                "content": {
                                    "createdAt": "2023-01-10T12:00:00Z",
                                    "closedAt": "2023-02-01T09:00:00Z",
                                },
                            },
                            {
                                "id": "PVTI_open",
                                "content": {
                                    "createdAt": "2023-03-05T08:00:00Z",
                                    "closedAt": None,
                                },
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    set_field_response = unittest.mock.MagicMock()
    set_field_response.status_code = 200
    set_field_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_closed"}}}
    }

    # project_info, list_items, then 4 date sets (2 items × 2 fields each)
    response_sequence = [
        project_info_response,
        list_items_response,
        set_field_response,  # item1 start date
        set_field_response,  # item1 end date
        set_field_response,  # item2 start date
        set_field_response,  # item2 end date
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        update_project_item_dates(
            project_url="https://github.com/users/testuser/projects/1",
            end_date_placeholder_days=30,
        )

    # 6 total calls
    assert mock_post.call_count == 6

    # Verify item1 (closed) dates
    item1_start = mock_post.call_args_list[2].kwargs["json"]["variables"]
    assert item1_start["itemId"] == "PVTI_closed"
    assert item1_start["fieldId"] == "PVTF_start"
    assert item1_start["date"] == "2023-01-10"

    item1_end = mock_post.call_args_list[3].kwargs["json"]["variables"]
    assert item1_end["itemId"] == "PVTI_closed"
    assert item1_end["fieldId"] == "PVTF_end"
    assert item1_end["date"] == "2023-02-01"

    # Verify item2 (open) uses placeholder end date (2023-03-05 + 30 = 2023-04-04)
    item2_start = mock_post.call_args_list[4].kwargs["json"]["variables"]
    assert item2_start["itemId"] == "PVTI_open"
    assert item2_start["fieldId"] == "PVTF_start"
    assert item2_start["date"] == "2023-03-05"

    item2_end = mock_post.call_args_list[5].kwargs["json"]["variables"]
    assert item2_end["itemId"] == "PVTI_open"
    assert item2_end["fieldId"] == "PVTF_end"
    assert item2_end["date"] == "2023-04-04"


def test_list_project_items_with_dates_returns_items() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "content": {
                                    "createdAt": "2023-01-01T00:00:00Z",
                                    "closedAt": "2023-06-01T00:00:00Z",
                                },
                            },
                            {"id": "PVTI_no_content", "content": None},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        items = _list_project_items_with_dates(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            headers={"Authorization": "token fake-token"},
        )

    assert len(items) == 1
    assert items[0]["id"] == "PVTI_1"
    assert items[0]["createdAt"] == "2023-01-01T00:00:00Z"
    assert items[0]["closedAt"] == "2023-06-01T00:00:00Z"


def test_list_project_item_content_urls_returns_urls() -> None:
    """_list_project_item_content_urls returns the set of content URLs already in the project."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {"content": {"url": "https://github.com/owner/repo/pull/1"}},
                            {"content": {"url": "https://github.com/owner/repo/issues/2"}},
                            {"content": None},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        urls = _list_project_item_content_urls(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            headers={"Authorization": "token fake-token"},
        )

    assert urls == {
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/issues/2",
    }


def test_list_project_item_content_urls_returns_empty_set_when_no_items() -> None:
    """_list_project_item_content_urls returns an empty set when the project has no items."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        urls = _list_project_item_content_urls(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            headers={"Authorization": "token fake-token"},
        )

    assert urls == set()


def test_add_to_project_skips_items_already_in_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Items whose URLs are already in the project are excluded and not re-added."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    existing_pr_url = "https://github.com/owner/repo/pull/1"
    new_pr_url = "https://github.com/owner/repo/pull/2"
    (tmp_path / "urls.json").write_text(json.dumps([existing_pr_url, new_pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            }
                        ]
                    },
                }
            }
        }
    }

    list_urls_response = unittest.mock.MagicMock()
    list_urls_response.status_code = 200
    list_urls_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {"content": {"url": existing_pr_url}},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR2_node_id",
                "state": "CLOSED",
                "createdAt": "2023-05-01T00:00:00Z",
                "closedAt": "2023-06-01T00:00:00Z",
            }
        }
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {
        "data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}
    }

    set_status_response = unittest.mock.MagicMock()
    set_status_response.status_code = 200
    set_status_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}}
    }

    # Only new_pr_url should be processed: project_info, list_urls, item_info, add_item, set_status
    response_sequence = [
        project_info_response,
        list_urls_response,
        item_info_response,
        add_item_response,
        set_status_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        my_work_history.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
        )

    # 5 calls: project_info, list_urls, item_info (for new_pr only), add_item, set_status
    assert mock_post.call_count == 5

    # Verify the item_info call was for new_pr_url, not existing_pr_url
    item_info_call = mock_post.call_args_list[2]
    assert item_info_call.kwargs["json"]["variables"]["url"] == new_pr_url

    # Verify add_item was called with the node ID for the new item only
    add_item_call = mock_post.call_args_list[3]
    assert add_item_call.kwargs["json"]["variables"]["contentId"] == "PR2_node_id"


# ---------------------------------------------------------------------------
# Integration tests – require a real GITHUB_TOKEN
# ---------------------------------------------------------------------------

_SKIP_INTEGRATION = pytest.mark.skipif(
    not _has_valid_github_token(),
    reason="GITHUB_TOKEN not set or is a placeholder; skipping integration tests",
)


@_SKIP_INTEGRATION
def test_add_to_project_integration(tmp_path: pathlib.Path) -> None:
    """
    Integration test: adds a known closed PR to the test project, verifies it
    was added, then removes it so the project stays clean.
    """
    headers = _make_headers()

    # Resolve the project node ID (needed for cleanup mutations).
    try:
        project_id, _, _, _, _ = _get_project_info(project_url=_TEST_PROJECT_URL, headers=headers)
    except (PermissionError, RuntimeError) as exc:
        pytest.skip(str(exc))

    # Pre-clean: remove the test PR from the project if it is already present
    # (e.g. from a previous run where cleanup was skipped).
    try:
        items_with_urls = _list_project_items_with_urls(headers=headers)
    except PermissionError as exc:
        pytest.skip(str(exc))
    if _KNOWN_CLOSED_PR_URL in items_with_urls:
        _delete_project_item(
            project_id=project_id,
            item_id=items_with_urls[_KNOWN_CLOSED_PR_URL],
            headers=headers,
        )
        time.sleep(1)  # Brief pause to let the delete propagate.

    (tmp_path / "urls.json").write_text(json.dumps([_KNOWN_CLOSED_PR_URL]))

    # Capture warnings so they appear in the failure message if the assertion fails.
    with _warnings_module.catch_warnings(record=True) as caught_warnings:
        _warnings_module.simplefilter("always")
        my_work_history.add_to_project(directory=tmp_path, project_url=_TEST_PROJECT_URL)
    warning_messages = [str(w.message) for w in caught_warnings]

    # Poll for the newly-added item with retries to handle GitHub API replication lag.
    added_item_id = None
    items_after: dict[str, str] = {}
    for attempt in range(6):
        items_after = _list_project_items_with_urls(headers=headers)
        added_item_id = items_after.get(_KNOWN_CLOSED_PR_URL)
        if added_item_id is not None:
            break
        time.sleep(2)

    diagnostic = (
        f"Warnings during add_to_project: {warning_messages}\n"
        f"URLs in project after (first 10): {list(items_after.keys())[:10]}"
    )

    try:
        assert added_item_id is not None, (
            f"Expected {_KNOWN_CLOSED_PR_URL!r} to be present in the project after add_to_project.\n{diagnostic}"
        )
    finally:
        # Always clean up, even if the assertion fails.
        if added_item_id is not None:
            _delete_project_item(project_id=project_id, item_id=added_item_id, headers=headers)
