import unittest.mock

import my_work_history
import pytest
from my_work_history._create_project import _get_owner_node_id


def test_create_project_page_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        my_work_history.create_project_page(owner="some-owner", title="Some Project")


def test_get_owner_node_id_raises_for_unknown_owner() -> None:
    headers = {"Authorization": "token fake-token"}

    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 404

    with unittest.mock.patch("requests.get", return_value=mock_response):
        with pytest.raises(ValueError, match="Could not resolve GitHub node ID"):
            _get_owner_node_id(owner="nonexistent-owner-xyz", headers=headers)


def test_create_project_page_returns_id_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    mock_user_response = unittest.mock.MagicMock()
    mock_user_response.status_code = 200
    mock_user_response.json.return_value = {"node_id": "U_kgDOA"}

    mock_graphql_response = unittest.mock.MagicMock()
    mock_graphql_response.status_code = 200
    mock_graphql_response.json.return_value = {
        "data": {
            "createProjectV2": {
                "projectV2": {
                    "id": "PVT_kwDOA",
                    "url": "https://github.com/orgs/some-owner/projects/1",
                }
            }
        }
    }

    with unittest.mock.patch("requests.get", return_value=mock_user_response), unittest.mock.patch(
        "requests.post", return_value=mock_graphql_response
    ):
        result = my_work_history.create_project_page(owner="some-owner", title="My Project")

    assert result == {"id": "PVT_kwDOA", "url": "https://github.com/orgs/some-owner/projects/1"}


def test_create_project_page_returns_empty_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    mock_user_response = unittest.mock.MagicMock()
    mock_user_response.status_code = 200
    mock_user_response.json.return_value = {"node_id": "U_kgDOA"}

    mock_graphql_response = unittest.mock.MagicMock()
    mock_graphql_response.status_code = 403
    mock_graphql_response.json.return_value = {"message": "rate limit exceeded"}

    with unittest.mock.patch("requests.get", return_value=mock_user_response), unittest.mock.patch(
        "requests.post", return_value=mock_graphql_response
    ):
        with pytest.warns(UserWarning):
            result = my_work_history.create_project_page(owner="some-owner", title="My Project")

    assert result == {}

