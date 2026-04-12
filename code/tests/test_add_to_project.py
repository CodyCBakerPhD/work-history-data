import json
import os
import pathlib
import unittest.mock

import pytest
import requests

import my_work_history
from my_work_history._add_to_project import (
    _add_item_to_project,
    _check_graphql_response,
    _collect_unique_urls,
    _get_item_info,
    _get_project_info,
    _set_item_status,
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


def _list_project_item_ids(headers: dict[str, str]) -> set[str]:
    """Return the set of item IDs currently in the test project.

    Raises
    ------
    PermissionError
        If the API returns 403 (token lacks project permissions).
    """
    query = """
query($login: String!, $number: Int!) {
    user(login: $login) {
        projectV2(number: $number) {
            items(first: 100) {
                nodes { id }
            }
        }
    }
}
"""
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": {"login": "CodyCBakerPhD", "number": 5}},
        headers=headers,
    )
    if response.status_code == 403:
        raise PermissionError("GitHub token lacks project permissions (403)")
    result = response.json()
    nodes = result["data"]["user"]["projectV2"]["items"]["nodes"]
    return {node["id"] for node in nodes}


def _list_project_items_with_urls(headers: dict[str, str]) -> dict[str, str]:
    """Return a mapping of {content_url: item_id} for items in the test project."""
    query = """
query($login: String!, $number: Int!) {
    user(login: $login) {
        projectV2(number: $number) {
            items(first: 100) {
                nodes {
                    id
                    content {
                        ... on PullRequest { url }
                        ... on Issue { url }
                    }
                }
            }
        }
    }
}
"""
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": {"login": "CodyCBakerPhD", "number": 5}},
        headers=headers,
    )
    if response.status_code == 403:
        raise PermissionError("GitHub token lacks project permissions (403)")
    result = response.json()
    nodes = result["data"]["user"]["projectV2"]["items"]["nodes"]
    return {
        node["content"]["url"]: node["id"]
        for node in nodes
        if node.get("content") and node["content"].get("url")
    }


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
                            }
                        ]
                    },
                }
            }
        }
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        project_id, status_field_id, status_options = _get_project_info(
            project_url="https://github.com/users/testuser/projects/1",
            headers=headers,
        )

    assert project_id == "PVT_kwDOA"
    assert status_field_id == "PVTSSF_id"
    assert status_options == {"Todo": "opt1", "In Progress": "opt2", "Done": "opt3"}


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
        "data": {"resource": {"id": "PR_node_id", "state": "CLOSED"}}
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        node_id, item_type, item_state = _get_item_info(
            url="https://github.com/owner/repo/pull/1", headers=headers
        )

    assert node_id == "PR_node_id"
    assert item_type == "PullRequest"
    assert item_state == "closed"


def test_get_item_info_classifies_issue() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"resource": {"id": "ISSUE_node_id", "state": "OPEN"}}
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        node_id, item_type, item_state = _get_item_info(
            url="https://github.com/owner/repo/issues/5", headers=headers
        )

    assert node_id == "ISSUE_node_id"
    assert item_type == "Issue"
    assert item_state == "open"


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
        "data": {"resource": {"id": "PR_node_id", "state": "CLOSED"}}
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

    response_sequence = [project_info_response, item_info_response, add_item_response, set_status_response]

    with unittest.mock.patch("requests.post", side_effect=response_sequence):
        my_work_history.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
        )


def test_add_to_project_skips_url_with_null_resource(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Items that return a null resource are skipped with a warning."""
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

    with unittest.mock.patch(
        "requests.post", side_effect=[project_info_response, null_resource_response]
    ):
        with pytest.warns(UserWarning, match="did not resolve"):
            my_work_history.add_to_project(
                directory=tmp_path,
                project_url="https://github.com/users/testuser/projects/1",
            )


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
        project_id, _, _ = _get_project_info(project_url=_TEST_PROJECT_URL, headers=headers)
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

    # Record which items already exist so we only clean up what we add.
    items_before = _list_project_item_ids(headers=headers)

    (tmp_path / "urls.json").write_text(json.dumps([_KNOWN_CLOSED_PR_URL]))

    my_work_history.add_to_project(directory=tmp_path, project_url=_TEST_PROJECT_URL)

    items_after = _list_project_item_ids(headers=headers)
    new_item_ids = items_after - items_before

    try:
        assert new_item_ids, "Expected at least one item to be added to the project"
    finally:
        # Always clean up, even if the assertion fails.
        for item_id in new_item_ids:
            _delete_project_item(project_id=project_id, item_id=item_id, headers=headers)
