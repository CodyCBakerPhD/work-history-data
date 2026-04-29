import datetime
import json
import os
import pathlib
import warnings

import requests
import tqdm


def add_to_project(
    directory: pathlib.Path,
    project_url: str,
    status: str | None = None,
    end_date_placeholder_days: int = 180,
) -> None:
    """
    Add all unique URLs from the derivatives directory to a GitHub Project (v2).

    Items that are already present in the project are automatically skipped.

    For each new item:
    - If ``status`` is provided, all items are assigned that status value.
    - Otherwise, the status is derived from the item type and state:
      - If the Issue or PR is closed, it is given the 'Done' status.
      - If the item is an open PR, it is given the 'In Progress' status.
      - If the item is an open Issue, it is given the 'Todo' status.
    - The start date is set to the item's creation date.
    - The end date is set to the item's closed date (if closed), or to
      ``end_date_placeholder_days`` days after the creation date otherwise.

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
    end_date_placeholder_days : int, optional
        Number of days after the item's creation date to use as the placeholder end date
        when the item has not yet been closed. Default is 180 (approximately 6 months).
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

    # Resolve the project node ID and get Status / date field info
    project_id, status_field_id, status_options, start_date_field_id, end_date_field_id = _get_project_info(
        project_url=project_url, headers=headers
    )

    # Parse owner type, login, and number from URL
    parts = project_url.rstrip("/").split("/")
    owner_type = parts[3]
    owner_login = parts[4]
    project_number = int(parts[6])

    # Fetch existing project item URLs to skip items already present in the project
    existing_urls = _list_project_item_content_urls(
        owner_type=owner_type,
        owner_login=owner_login,
        project_number=project_number,
        headers=headers,
    )

    # Exclude items already in the project
    new_urls = [url for url in all_urls if url not in existing_urls]

    for url in tqdm.tqdm(iterable=new_urls, desc="Adding items to project", unit="items", dynamic_ncols=True):
        # Determine the item type, state, and dates from the URL
        item_info = _get_item_info(url=url, headers=headers)
        if item_info is None:
            continue
        item_node_id, item_type, item_state, created_at, closed_at = item_info

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

        # Set start date (item creation date)
        if start_date_field_id is not None:
            start_date = created_at[:10]  # Extract YYYY-MM-DD from ISO datetime
            _set_item_date(
                project_id=project_id,
                item_id=item_id,
                field_id=start_date_field_id,
                date=start_date,
                headers=headers,
            )

        # Set end date (closed date, or placeholder)
        if end_date_field_id is not None:
            if closed_at is not None:
                end_date = closed_at[:10]
            else:
                creation_date = datetime.date.fromisoformat(created_at[:10])
                end_date = (creation_date + datetime.timedelta(days=end_date_placeholder_days)).isoformat()
            _set_item_date(
                project_id=project_id,
                item_id=item_id,
                field_id=end_date_field_id,
                date=end_date,
                headers=headers,
            )


def _collect_unique_urls(directory: pathlib.Path) -> list[str]:
    """Collect all unique URLs from JSON files under the given directory."""
    all_info_file_paths = list(directory.rglob(pattern="*.json"))
    all_urls: set[str] = set()
    for info_file_path in all_info_file_paths:
        with info_file_path.open(mode="r") as file_stream:
            info = json.load(file_stream)
        if isinstance(info, dict):
            # REST API format: {"total_count": ..., "items": [{"html_url": ...}, ...], ...}
            for item in info.get("items", []):
                if isinstance(item, dict) and "html_url" in item:
                    all_urls.add(item["html_url"])
        else:
            # GraphQL format: a list of URL strings
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
) -> tuple[str, str, dict[str, str], str | None, str | None]:
    """
    Retrieve the project node ID, the Status field ID, available Status option names/IDs,
    and the IDs of the "Start date" and "End date" date fields (if present).

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    tuple[str, str, dict[str, str], str | None, str | None]
        A tuple of (project_id, status_field_id, status_options, start_date_field_id,
        end_date_field_id) where status_options maps option name → option ID, and
        start_date_field_id / end_date_field_id are the IDs of the project's "Start date"
        and "End date" date fields respectively (or None if not present).
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
                    ... on ProjectV2Field {
                        id
                        name
                        dataType
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
                    ... on ProjectV2Field {
                        id
                        name
                        dataType
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

    # Find the Status, Start date, and End date fields
    status_field_id = None
    status_options: dict[str, str] = {}
    start_date_field_id = None
    end_date_field_id = None

    for field in project_data["fields"]["nodes"]:
        if not field:
            continue
        field_name = field.get("name", "")
        if field_name == "Status":
            status_field_id = field["id"]
            for option in field.get("options", []):
                status_options[option["name"]] = option["id"]
        elif field.get("dataType") == "DATE" and field_name == "Start date":
            start_date_field_id = field["id"]
        elif field.get("dataType") == "DATE" and field_name == "End date":
            end_date_field_id = field["id"]

    if status_field_id is None:
        message = f"No 'Status' field found in project `{project_url}`."
        raise ValueError(message)

    return project_id, status_field_id, status_options, start_date_field_id, end_date_field_id


def _get_item_info(url: str, headers: dict[str, str]) -> tuple[str, str, str, str, str | None] | None:
    """
    Fetch the node ID, type (PullRequest or Issue), state, creation date, and closed date for the given URL.

    Parameters
    ----------
    url : str
        The GitHub URL of the PR or Issue.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    tuple[str, str, str, str, str | None] or None
        A tuple of (node_id, item_type, item_state, created_at, closed_at) where item_type is
        'PullRequest' or 'Issue', item_state is 'open' or 'closed', created_at is an ISO 8601
        datetime string, and closed_at is an ISO 8601 datetime string or None if not closed.
        Returns None if the URL does not resolve to a PR or Issue.
    """
    query = """
query GetItem($url: URI!) {
    resource(url: $url) {
        ... on PullRequest {
            id
            state
            createdAt
            closedAt
        }
        ... on Issue {
            id
            state
            createdAt
            closedAt
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
    created_at: str = resource["createdAt"]
    closed_at: str | None = resource.get("closedAt")

    # Determine the type based on the URL path
    item_type = "PullRequest" if "/pull/" in url else "Issue"

    return node_id, item_type, item_state, created_at, closed_at


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


def _set_item_date(
    project_id: str,
    item_id: str,
    field_id: str,
    date: str,
    headers: dict[str, str],
) -> None:
    """
    Set a date field of a project item.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    item_id : str
        The project item ID.
    field_id : str
        The global node ID of the date field.
    date : str
        The date value in ISO format (``YYYY-MM-DD``).
    headers : dict[str, str]
        HTTP headers including the Authorization token.
    """
    mutation = """
mutation SetDate($projectId: ID!, $itemId: ID!, $fieldId: ID!, $date: Date!) {
    updateProjectV2ItemFieldValue(
        input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { date: $date }
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
        "date": date,
    }
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
    )
    try:
        _check_graphql_response(
            response=response,
            context=f"Failed to set date for item `{item_id}` in project `{project_id}`.",
        )
    except RuntimeError:
        if response.status_code != 403:
            raise


def update_project_item_dates(
    project_url: str,
    end_date_placeholder_days: int = 180,
) -> None:
    """
    Update the start and end date fields on all items already added to a GitHub Project (v2).

    For each item in the project:
    - The start date field ("Start date") is set to the item's creation date.
    - The end date field ("End date") is set to the item's closed date (if closed),
      or to ``end_date_placeholder_days`` days after the creation date otherwise.

    If the project does not have a "Start date" or "End date" field, those updates are skipped.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.
    end_date_placeholder_days : int, optional
        Number of days after the item's creation date to use as the placeholder end date
        when the item has not yet been closed. Default is 180 (approximately 6 months).
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)

    headers = {"Authorization": f"token {github_token}"}

    project_id, _status_field_id, _status_options, start_date_field_id, end_date_field_id = _get_project_info(
        project_url=project_url, headers=headers
    )

    if start_date_field_id is None and end_date_field_id is None:
        warnings.warn(
            message=(
                f"Project `{project_url}` has no 'Start date' or 'End date' fields. "
                "No date updates were performed."
            ),
            stacklevel=2,
        )
        return

    # Parse owner type, login, and number from URL for the items query
    parts = project_url.rstrip("/").split("/")
    owner_type = parts[3]
    owner_login = parts[4]
    project_number = int(parts[6])

    # Collect all project items with their content dates (paginated)
    all_items = _list_project_items_with_dates(
        owner_type=owner_type,
        owner_login=owner_login,
        project_number=project_number,
        headers=headers,
    )

    for item in tqdm.tqdm(iterable=all_items, desc="Updating item dates", unit="items", dynamic_ncols=True):
        item_id = item["id"]
        created_at: str = item["createdAt"]
        closed_at: str | None = item.get("closedAt")

        if start_date_field_id is not None:
            start_date = created_at[:10]
            _set_item_date(
                project_id=project_id,
                item_id=item_id,
                field_id=start_date_field_id,
                date=start_date,
                headers=headers,
            )

        if end_date_field_id is not None:
            if closed_at is not None:
                end_date = closed_at[:10]
            else:
                creation_date = datetime.date.fromisoformat(created_at[:10])
                end_date = (creation_date + datetime.timedelta(days=end_date_placeholder_days)).isoformat()
            _set_item_date(
                project_id=project_id,
                item_id=item_id,
                field_id=end_date_field_id,
                date=end_date,
                headers=headers,
            )


def _list_project_item_content_urls(
    owner_type: str,
    owner_login: str,
    project_number: int,
    headers: dict[str, str],
) -> set[str]:
    """
    Return the set of content URLs for all items already in the project.

    Parameters
    ----------
    owner_type : str
        Either ``'users'`` or ``'orgs'``.
    owner_login : str
        The GitHub login of the project owner.
    project_number : int
        The number of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    set[str]
        A set of content URLs (PR or Issue URLs) for all items currently in the project.
    """
    if owner_type == "users":
        query = """
query GetItemUrls($login: String!, $number: Int!, $after: String) {
    user(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    content {
                        ... on PullRequest { url }
                        ... on Issue { url }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
"""
        data_path = ["data", "user", "projectV2", "items"]
    else:
        query = """
query GetItemUrls($login: String!, $number: Int!, $after: String) {
    organization(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    content {
                        ... on PullRequest { url }
                        ... on Issue { url }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
"""
        data_path = ["data", "organization", "projectV2", "items"]

    existing_urls: set[str] = set()
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = requests.post(
            url="https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
        )
        result = _check_graphql_response(
            response=response,
            context=f"Failed to list project item URLs for project {project_number}.",
        )
        items_data = result
        for key in data_path:
            items_data = items_data[key]

        for node in items_data["nodes"]:
            content = node.get("content")
            if content and "url" in content:
                existing_urls.add(content["url"])

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return existing_urls


def _list_project_items_with_dates(
    owner_type: str,
    owner_login: str,
    project_number: int,
    headers: dict[str, str],
) -> list[dict]:
    """
    Return all project items with their content creation and close dates.

    Parameters
    ----------
    owner_type : str
        Either ``'users'`` or ``'orgs'``.
    owner_login : str
        The GitHub login of the project owner.
    project_number : int
        The number of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    list[dict]
        A list of dicts, each with keys ``id``, ``createdAt``, and optionally ``closedAt``.
    """
    if owner_type == "users":
        query = """
query GetItems($login: String!, $number: Int!, $after: String) {
    user(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    content {
                        ... on PullRequest { createdAt closedAt }
                        ... on Issue { createdAt closedAt }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
"""
        data_path = ["data", "user", "projectV2", "items"]
    else:
        query = """
query GetItems($login: String!, $number: Int!, $after: String) {
    organization(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    content {
                        ... on PullRequest { createdAt closedAt }
                        ... on Issue { createdAt closedAt }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
"""
        data_path = ["data", "organization", "projectV2", "items"]

    all_items = []
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = requests.post(
            url="https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
        )
        result = _check_graphql_response(
            response=response,
            context=f"Failed to list project items for project {project_number}.",
        )
        items_data = result
        for key in data_path:
            items_data = items_data[key]

        for node in items_data["nodes"]:
            content = node.get("content")
            if content and "createdAt" in content:
                all_items.append(
                    {
                        "id": node["id"],
                        "createdAt": content["createdAt"],
                        "closedAt": content.get("closedAt"),
                    }
                )

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return all_items


def _list_project_items_with_status(
    owner_type: str,
    owner_login: str,
    project_number: int,
    status_field_id: str,
    headers: dict[str, str],
) -> list[dict]:
    """
    Return all project items together with their current status option ID.

    Parameters
    ----------
    owner_type : str
        Either ``'users'`` or ``'orgs'``.
    owner_login : str
        The GitHub login of the project owner.
    project_number : int
        The number of the GitHub Project v2.
    status_field_id : str
        The global node ID of the Status field.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    list[dict]
        A list of dicts, each with keys ``id`` and ``status_option_id``.
        Items whose status field value cannot be determined have ``status_option_id`` set to ``None``.
    """
    if owner_type == "users":
        query = """
query GetItemsWithStatus($login: String!, $number: Int!, $after: String) {
    user(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    fieldValues(first: 20) {
                        nodes {
                            ... on ProjectV2ItemFieldSingleSelectValue {
                                optionId
                                field {
                                    ... on ProjectV2SingleSelectField {
                                        id
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
"""
        data_path = ["data", "user", "projectV2", "items"]
    else:
        query = """
query GetItemsWithStatus($login: String!, $number: Int!, $after: String) {
    organization(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    fieldValues(first: 20) {
                        nodes {
                            ... on ProjectV2ItemFieldSingleSelectValue {
                                optionId
                                field {
                                    ... on ProjectV2SingleSelectField {
                                        id
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
"""
        data_path = ["data", "organization", "projectV2", "items"]

    all_items = []
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = requests.post(
            url="https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
        )
        result = _check_graphql_response(
            response=response,
            context=f"Failed to list project items with status for project {project_number}.",
        )
        items_data = result
        for key in data_path:
            items_data = items_data[key]

        for node in items_data["nodes"]:
            item_id = node["id"]
            status_option_id = None
            for field_value in node.get("fieldValues", {}).get("nodes", []):
                if not field_value:
                    continue
                field = field_value.get("field", {})
                if field and field.get("id") == status_field_id:
                    status_option_id = field_value.get("optionId")
                    break
            all_items.append({"id": item_id, "status_option_id": status_option_id})

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return all_items


def move_done_to_history(project_url: str) -> None:
    """
    Move all items with ``Status=Done`` to ``Status=History`` in a GitHub Project (v2).

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set, or if the project
        does not have a ``'Done'`` or ``'History'`` status option.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)

    headers = {"Authorization": f"token {github_token}"}

    project_id, status_field_id, status_options, _start_date_field_id, _end_date_field_id = _get_project_info(
        project_url=project_url, headers=headers
    )

    done_option_id = status_options.get("DONE")
    if done_option_id is None:
        message = (
            f"Status option 'DONE' not found in project `{project_url}`. "
            f"Available options: {list(status_options.keys())}."
        )
        raise ValueError(message)

    history_option_id = status_options.get("History")
    if history_option_id is None:
        message = (
            f"Status option 'History' not found in project `{project_url}`. "
            f"Available options: {list(status_options.keys())}."
        )
        raise ValueError(message)

    # Parse owner type, login, and number from URL
    parts = project_url.rstrip("/").split("/")
    owner_type = parts[3]
    owner_login = parts[4]
    project_number = int(parts[6])

    # Fetch all items with their current status
    all_items = _list_project_items_with_status(
        owner_type=owner_type,
        owner_login=owner_login,
        project_number=project_number,
        status_field_id=status_field_id,
        headers=headers,
    )

    done_items = [item for item in all_items if item["status_option_id"] == done_option_id]

    for item in tqdm.tqdm(
        iterable=done_items, desc="Moving items from DONE to History", unit="items", dynamic_ncols=True
    ):
        _set_item_status(
            project_id=project_id,
            item_id=item["id"],
            field_id=status_field_id,
            option_id=history_option_id,
            headers=headers,
        )

