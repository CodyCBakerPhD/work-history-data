"""Fetch all pull requests created by a GitHub user."""

from typing import Any

from .base import GitHubFetcher


def fetch_pull_requests(token: str, username: str, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch all pull requests created by the user across all repositories.

    Parameters
    ----------
    token : str
        GitHub personal access token
    username : str
        GitHub username
    start_date : str, optional
        ISO 8601 format date (YYYY-MM-DD) to filter from
    end_date : str, optional
        ISO 8601 format date (YYYY-MM-DD) to filter to

    Returns
    -------
    list[dict]
        List of all pull requests created by the user
    """
    fetcher = GitHubFetcher(token, username, start_date, end_date)

    date_range_str = ""
    if start_date or end_date:
        date_range_str = f" (date range: {start_date or 'start'} to {end_date or 'now'})"
    print(f"Fetching pull requests created by {username}{date_range_str}...")

    # Use GitHub search API to find all PRs by the user
    url = f"{fetcher.base_url}/search/issues"
    query = f"author:{username} type:pr{fetcher._build_date_range_query()}"
    params = {"q": query, "sort": "created", "order": "desc"}

    pull_requests = fetcher.search_paginated(url, params)

    print(f"Total pull requests fetched: {len(pull_requests)}")
    return pull_requests
