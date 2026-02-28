import functools
import os
import re
import typing
import warnings

import requests


def fetch_info_for_date(
    info_type: typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"],
    date: str,
    username: str,
    request_type: typing.Literal["rest", "graphql"],
) -> tuple[list[dict[str, typing.Any | list[dict[str, typing.Any]]]], bool]:
    """
    Fetch GitHub info (issues, PRs, etc.) created by a specific user on a specific date.

    Parameters
    ----------
    info_type : Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"]
        The type of GitHub info to fetch.
    date : str
        The date for which to fetch GitHub info, in ISO format (e.g., "2026-01-01").
    username : str
        The GitHub username for which to fetch info.

    Returns
    -------
    list[dict]
        A list of dictionaries containing the GitHub info for the specified date and user.
    bool
        Whether or not the GitHub API rate limit was hit during the query.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)
    if re.match(pattern=r"^\d{4}-\d{2}-\d{2}$", string=date) is None:
        message = (
            f"\nDate `{date}` is not in the correct format!\n"
            "Please provide a date in ISO format (e.g., '2026-01-01').\n\n"
        )
        raise ValueError(message)

    if request_type == "rest":
        result, hit_rate_limit = _fetch_info_for_date_rest(
            info_type=info_type,
            date=date,
            username=username,
            token=github_token,
        )
    else:
        result, hit_rate_limit = _fetch_info_for_date_graphql(
            info_type=info_type,
            date=date,
            username=username,
            token=github_token,
        )

    return result, hit_rate_limit


@functools.cache
def _format_rest_queries(date: str, username: str) -> dict[str, dict[str, str]]:
    entities_to_url_and_rest_query_mapping = {
        "prs_opened": {
            "url": "https://api.github.com/search/issues",
            "query": f"author:{username} type:pr created:{date}T00:00:00..{date}T23:59:59",
        },
        "prs_assigned": {
            "url": "https://api.github.com/search/issues",
            "query": f"assignee:{username} type:pr assigned:{date}T00:00:00..{date}T23:59:59",
        },
        "issues_opened": {
            "url": "https://api.github.com/search/issues",
            "query": f"author:{username} type:issue created:{date}T00:00:00..{date}T23:59:59",
        },
        "issues_assigned": {
            "url": "https://api.github.com/search/issues",
            "query": f"assignee:{username} type:issue assigned:{date}T00:00:00..{date}T23:59:59",
        },
    }
    return entities_to_url_and_rest_query_mapping


def _fetch_info_for_date_rest(
    info_type: typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"],
    date: str,
    username: str,
    token: str,
) -> tuple[list[dict[str, typing.Any | list[dict[str, typing.Any]]]], bool]:
    entities_to_url_and_rest_query_mapping = _format_rest_queries(date=date, username=username)

    url = entities_to_url_and_rest_query_mapping[info_type]["url"]
    query = entities_to_url_and_rest_query_mapping[info_type]["query"]
    response = requests.get(url=url, headers={"Authorization": f"token {token}"}, params={"q": query})
    status = response.status_code
    result = response.json()

    if result["incomplete_results"] is True:
        message = (
            f"GitHub REST API query `{query}` to URL `{url}` returned incomplete results! Please investigate."
            f"\nStatus code {status}: {result}"
        )
        raise RuntimeError(message)

    message = f"GitHub REST API query `{query}` to URL `{url}` failed!\n" f"Status code {status}: {result}"
    hit_rate_limit = False
    if status == 403:
        hit_rate_limit = True
        warnings.warn(message=message, stacklevel=2)
    elif status != 200:
        raise RuntimeError(message)

    return result, hit_rate_limit


@functools.cache
def _format_graphql_queries(date: str, username: str) -> dict[str, dict[str, str]]:
    entities_to_graphql_query_template = {
        "prs_opened": """
query OpenPRs($first: Int!) {
    search(
        query: "author:{username} type:pr created:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges {
            node {
                ... on PullRequest {
                    url
                }
            }
        }
    }
}
""",
        "prs_assigned": (
            """
query AssignedPRs($first: Int!) {
    search(
        query: "assignee:{username} type:pr assigned:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on PullRequest { url } } }
    }
}
"""
        ),
        "issues_opened": (
            """
query OpenIssues($first: Int!) {
    search(
        query: "author:{username} type:issue created:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on Issue { url } } }
    }
}
"""
        ),
        "issues_assigned": (
            """
query AssignedIssues($first: Int!) {
    search(
        query: "assignee:{username} type:issue assigned:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on Issue { url } } }
    }
}
"""
        ),
    }

    entities_to_graphql_query_mapping = dict()
    for entity, query_template in entities_to_graphql_query_template.items():
        query = query_template.replace("{username}", username).replace("{date}", date)
        entities_to_graphql_query_mapping[entity] = query

    return entities_to_graphql_query_mapping


def _fetch_info_for_date_graphql(
    info_type: typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"],
    date: str,
    username: str,
    token: str,
) -> tuple[list[dict[str, typing.Any | list[dict[str, typing.Any]]]], bool]:
    entities_to_graphql_query_mapping = _format_graphql_queries(date=date, username=username)

    query = entities_to_graphql_query_mapping[info_type]
    variables = {
        "user": username,
        "date": date,
        "first": 100,  # Require by query, should be good enough for a single day
    }
    headers = {"Authorization": f"token {token}"}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
    )
    status = response.status_code
    result = response.json()

    message = f"GitHub GraphQL API query `{query}` failed!\n" f"Status code {status}: {result}"
    hit_rate_limit = False
    if status == 403:
        hit_rate_limit = True
        warnings.warn(message=message, stacklevel=2)
    elif "errors" in result or status != 200:
        raise RuntimeError(message)

    unpacked_result = [node["node"]["url"] for node in result["data"]["search"]["edges"]]
    return unpacked_result, hit_rate_limit
