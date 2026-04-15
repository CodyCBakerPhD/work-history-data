import os
import warnings

import requests


def create_project_page(owner: str, title: str) -> dict[str, str]:
    """
    Create a GitHub Project (v2) page for the specified owner.

    Parameters
    ----------
    owner : str
        The GitHub user or organization login under which to create the project.
    title : str
        The title of the new GitHub Project.

    Returns
    -------
    dict[str, str]
        A dictionary containing the ``"id"`` and ``"url"`` of the created project.
        Returns an empty dictionary if the GitHub API rate limit was hit (HTTP 403);
        a warning is also issued in that case.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)

    headers = {"Authorization": f"token {github_token}"}

    # Resolve the owner's global node ID (works for both users and organizations)
    owner_id = _get_owner_node_id(owner=owner, headers=headers)

    # Create the GitHub Project v2 via the GraphQL API
    mutation = """
mutation CreateProject($ownerId: ID!, $title: String!) {
    createProjectV2(input: {ownerId: $ownerId, title: $title}) {
        projectV2 {
            id
            url
        }
    }
}
"""
    variables = {"ownerId": owner_id, "title": title}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
    )
    status = response.status_code
    result = response.json()

    message = f"GitHub GraphQL API mutation to create project `{title}` failed!\nStatus code {status}: {result}"
    if status == 403:
        warnings.warn(message=message, stacklevel=2)
        return {}
    if "errors" in result or status != 200:
        raise RuntimeError(message)

    project = result["data"]["createProjectV2"]["projectV2"]
    project_id = project["id"]

    # Create the canonical date fields expected by the populate / update-dates commands
    _create_date_field(project_id=project_id, field_name="Start date", headers=headers)
    _create_date_field(project_id=project_id, field_name="End date", headers=headers)

    return {"id": project_id, "url": project["url"]}


def _create_date_field(project_id: str, field_name: str, headers: dict[str, str]) -> None:
    """
    Create a DATE field with the given name on a GitHub Project (v2).

    Parameters
    ----------
    project_id : str
        The global node ID of the project.
    field_name : str
        The name to assign to the new DATE field (e.g. ``"Start date"``).
    headers : dict[str, str]
        HTTP headers including the Authorization token.
    """
    mutation = """
mutation CreateField($projectId: ID!, $name: String!) {
    createProjectV2Field(input: {projectId: $projectId, dataType: DATE, name: $name}) {
        projectV2Field {
            ... on ProjectV2Field {
                id
                name
            }
        }
    }
}
"""
    variables = {"projectId": project_id, "name": field_name}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
    )
    status = response.status_code
    result = response.json()

    if "errors" in result or status != 200:
        message = f"GitHub GraphQL API mutation to create field `{field_name}` failed!\nStatus code {status}: {result}"
        raise RuntimeError(message)


def _get_owner_node_id(owner: str, headers: dict[str, str]) -> str:
    """
    Resolve the GitHub node ID for a user or organization login.

    Parameters
    ----------
    owner : str
        The GitHub user or organization login.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str
        The global node ID of the owner.
    """
    # Try user endpoint first, then organization endpoint
    for endpoint in (f"https://api.github.com/users/{owner}", f"https://api.github.com/orgs/{owner}"):
        response = requests.get(url=endpoint, headers=headers)
        if response.status_code == 200:
            return response.json()["node_id"]

    message = f"Could not resolve GitHub node ID for owner `{owner}`. Please verify the login is correct."
    raise ValueError(message)
