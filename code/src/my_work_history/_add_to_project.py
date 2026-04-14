import json
import os
import pathlib
import warnings

import requests


def add_to_project(directory: pathlib.Path, project_url: str, status: str | None = None) -> None:
    """
    Add all unique URLs from the derivatives directory to a GitHub Project (v2).

    For each item:
    - If ``status`` is provided, all items are assigned that status value.
    - Otherwise, the status is derived from the item type and state:
      - If the Issue or PR is closed, it is given the 'Done' status.
      - If the item is an open PR, it is given the 'In Progress' status.
      - If the item is an open Issue, it is given the 'Todo' status.

    Parameters
    ----------
    directory : pathlib.Path
        The directory containing the derivatives JSON files.
        Should be a specific request-type subdirectory,
        e.g., ``/path/to/version-0+1/username-codycbakerphd/request-graphql``.
    project_url : str
        The URL of the GitHub Project v2 to add items to,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.
    status : str or None, optional
        A custom status value to apply uniformly to all items added to the project.
        If ``None`` (the default), the status is derived from each item's type and state.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)

    headers = {"Authorization": f"token {github_token}"}

    # Collect all unique URLs from JSON files in the directory
    all_urls = _collect_unique_urls(directory=directory)

    if not all_urls:
        warnings.warn(message=f"No URLs found in directory `{directory}`.", stacklevel=2)
        return

    # Resolve the project node ID and get Status field info
    project_id, status_field_id, status_options = _get_project_info(project_url=project_url, headers=headers)

    for url in all_urls:
        # Determine the item type and state from the URL
        item_info = _get_item_info(url=url, headers=headers)
        if item_info is None:
            warnings.warn(message=f"URL `{url}` did not resolve to a PR or Issue; skipping.", stacklevel=2)
            continue
        item_node_id, item_type, item_state = item_info

        # Add the item to the project
        item_id = _add_item_to_project(project_id=project_id, content_id=item_node_id, headers=headers)
        if item_id is None:
            continue

        # Determine the correct status
        if status is not None:
            status_name = status
        else:
            status_name = {
                ("PullRequest", "closed"): "Done",
                ("PullRequest", "merged"): "Done",
                ("Issue", "closed"): "Done",
                ("PullRequest", "open"): "In Progress",
                ("Issue", "open"): "Todo",
            }.get((item_type, item_state))

        # Find the option ID for the desired status
        option_id = status_options.get(status_name)
        if option_id is None:
            message = (
                f"Status option `{status_name}` not found in project. "
                f"Available options: {list(status_options.keys())}."
            )
            warnings.warn(message=message, stacklevel=2)
            continue

        _set_item_status(
            project_id=project_id,
            item_id=item_id,
            field_id=status_field_id,
            option_id=option_id,
            headers=headers,
        )


def _collect_unique_urls(directory: pathlib.Path) -> list[str]:
    """Collect all unique URLs from JSON files under the given directory."""
    all_info_file_paths = list(directory.rglob(pattern="*.json"))
    all_urls: set[str] = set()
    for info_file_path in all_info_file_paths:
        with info_file_path.open(mode="r") as file_stream:
            info: list = json.load(file_stream)
        for value in info:
            all_urls.add(value)
    return list(all_urls)


def _check_graphql_response(response: requests.Response, context: str) -> dict:
    """
    Validate a GraphQL API response and raise or warn on errors.

    Parameters
    ----------
    response : requests.Response
        The HTTP response from the GitHub GraphQL API.
    context : str
        A descriptive label used in error/warning messages (e.g., the URL or mutation name).

    Returns
    -------
    dict
        The parsed JSON result from the response.

    Raises
    ------
    RuntimeError
        If the response indicates a non-403 error.
    """
    status = response.status_code
    result = response.json()
    message = f"{context}\nStatus code {status}: {result}"
    if status == 403:
        warnings.warn(message=message, stacklevel=3)
        raise RuntimeError(message)
    if "errors" in result or status != 200:
        raise RuntimeError(message)
    return result


def _get_project_info(
    project_url: str, headers: dict[str, str]
) -> tuple[str, str, dict[str, str]]:
    """
    Retrieve the project node ID, the Status field ID, and available Status option names/IDs.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    tuple[str, str, dict[str, str]]
        A tuple of (project_id, status_field_id, status_options) where
        status_options maps option name → option ID.
    """
    # Parse owner type, owner login, and project number from URL
    # Expected formats:
    #   https://github.com/users/{login}/projects/{number}
    #   https://github.com/orgs/{login}/projects/{number}
    parts = project_url.rstrip("/").split("/")
    # parts: ['https:', '', 'github.com', 'users'|'orgs', login, 'projects', number]
    owner_type = parts[3]  # 'users' or 'orgs'
    owner_login = parts[4]
    project_number = int(parts[6])

    if owner_type == "users":
        query = """
query GetProject($login: String!, $number: Int!) {
    user(login: $login) {
        projectV2(number: $number) {
            id
            fields(first: 20) {
                nodes {
                    ... on ProjectV2SingleSelectField {
                        id
                        name
                        options {
                            id
                            name
                        }
                    }
                }
            }
        }
    }
}
"""
        variables = {"login": owner_login, "number": project_number}
        data_path = ["data", "user", "projectV2"]
    else:
        query = """
query GetProject($login: String!, $number: Int!) {
    organization(login: $login) {
        projectV2(number: $number) {
            id
            fields(first: 20) {
                nodes {
                    ... on ProjectV2SingleSelectField {
                        id
                        name
                        options {
                            id
                            name
                        }
                    }
                }
            }
        }
    }
}
"""
        variables = {"login": owner_login, "number": project_number}
        data_path = ["data", "organization", "projectV2"]

    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
    )
    result = _check_graphql_response(response=response, context=f"Failed to retrieve project info for `{project_url}`.")

    project_data = result
    for key in data_path:
        project_data = project_data[key]

    project_id = project_data["id"]

    # Find the Status field
    status_field_id = None
    status_options: dict[str, str] = {}
    for field in project_data["fields"]["nodes"]:
        if not field:
            continue
        if field.get("name") == "Status":
            status_field_id = field["id"]
            for option in field.get("options", []):
                status_options[option["name"]] = option["id"]
            break

    if status_field_id is None:
        message = f"No 'Status' field found in project `{project_url}`."
        raise ValueError(message)

    return project_id, status_field_id, status_options


def _get_item_info(url: str, headers: dict[str, str]) -> tuple[str, str, str] | None:
    """
    Fetch the node ID, type (PullRequest or Issue), and state (open or closed) for the given URL.

    Parameters
    ----------
    url : str
        The GitHub URL of the PR or Issue.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    tuple[str, str, str] or None
        A tuple of (node_id, item_type, item_state) where item_type is
        'PullRequest' or 'Issue', and item_state is 'open' or 'closed'.
        Returns None if the URL does not resolve to a PR or Issue.
    """
    query = """
query GetItem($url: URI!) {
    resource(url: $url) {
        ... on PullRequest {
            id
            state
        }
        ... on Issue {
            id
            state
        }
    }
}
"""
    variables = {"url": url}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
    )
    result = _check_graphql_response(response=response, context=f"Failed to retrieve item info for URL `{url}`.")

    resource = result["data"]["resource"]
    if resource is None:
        return None
    node_id = resource["id"]
    item_state = resource["state"].lower()

    # Determine the type based on the URL path
    item_type = "PullRequest" if "/pull/" in url else "Issue"

    return node_id, item_type, item_state


def _add_item_to_project(project_id: str, content_id: str, headers: dict[str, str]) -> str | None:
    """
    Add an item to a GitHub Project v2 by its content node ID.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    content_id : str
        The global node ID of the PR or Issue to add.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str or None
        The project item ID if successful, or None if rate-limited.
    """
    mutation = """
mutation AddItem($projectId: ID!, $contentId: ID!) {
    addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item {
            id
        }
    }
}
"""
    variables = {"projectId": project_id, "contentId": content_id}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
    )
    try:
        result = _check_graphql_response(
            response=response,
            context=f"Failed to add item `{content_id}` to project `{project_id}`.",
        )
    except RuntimeError:
        if response.status_code == 403:
            return None
        raise

    return result["data"]["addProjectV2ItemById"]["item"]["id"]


def _set_item_status(
    project_id: str,
    item_id: str,
    field_id: str,
    option_id: str,
    headers: dict[str, str],
) -> None:
    """
    Set the Status field of a project item.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    item_id : str
        The project item ID.
    field_id : str
        The global node ID of the Status field.
    option_id : str
        The option ID for the desired status value.
    headers : dict[str, str]
        HTTP headers including the Authorization token.
    """
    mutation = """
mutation SetStatus($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
    updateProjectV2ItemFieldValue(
        input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { singleSelectOptionId: $optionId }
        }
    ) {
        projectV2Item {
            id
        }
    }
}
"""
    variables = {
        "projectId": project_id,
        "itemId": item_id,
        "fieldId": field_id,
        "optionId": option_id,
    }
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
    )
    try:
        _check_graphql_response(
            response=response,
            context=f"Failed to set status for item `{item_id}` in project `{project_id}`.",
        )
    except RuntimeError:
        if response.status_code != 403:
            raise

