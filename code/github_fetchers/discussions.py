"""Fetch all GitHub discussions comments by a user."""

from typing import Any

from .base import GitHubFetcher


def fetch_discussions(token: str, username: str, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch all discussions where the user has participated.

    Note: GitHub's REST API has limited support for discussions.
    This uses the search API to find discussions by the user.

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
        List of discussions where the user has participated
    """
    fetcher = GitHubFetcher(token, username, start_date, end_date)

    date_range_str = ""
    if start_date or end_date:
        date_range_str = f" (date range: {start_date or 'start'} to {end_date or 'now'})"
    print(f"Fetching discussions by {username}{date_range_str}...")
    print("Note: Discussion support via REST API is limited.")
    print("For comprehensive discussion data, consider using GitHub's GraphQL API.")

    # Use GitHub search API to find discussions by the user
    # This will find discussions authored by the user
    url = f"{fetcher.base_url}/search/issues"
    query = f"author:{username} is:discussion{fetcher._build_date_range_query()}"
    params = {"q": query, "sort": "created", "order": "desc"}

    discussions = fetcher.search_paginated(url, params)

    print(f"Total discussions fetched: {len(discussions)}")
    return discussions
