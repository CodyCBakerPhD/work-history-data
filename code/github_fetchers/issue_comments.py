"""Fetch all issue and PR comments by a GitHub user."""

from typing import Any

from .base import GitHubFetcher


def fetch_issue_comments(token: str, username: str, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch all issue and PR comments by the user across all repositories.

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
        List of all issue/PR comments by the user
    """
    fetcher = GitHubFetcher(token, username, start_date, end_date)

    date_range_str = ""
    if start_date or end_date:
        date_range_str = f" (date range: {start_date or 'start'} to {end_date or 'now'})"
    print(f"Fetching issue and PR comments by {username}{date_range_str}...")

    # Use GitHub search API to find all comments by the user
    url = f"{fetcher.base_url}/search/issues"
    query = f"commenter:{username}{fetcher._build_date_range_query()}"
    params = {"q": query, "sort": "created", "order": "desc"}

    comments = fetcher.search_paginated(url, params)

    print(f"Total issues/PRs with comments fetched: {len(comments)}")
    print("Note: This returns issues/PRs where you commented, not individual comments.")
    print("For detailed comment data, you may need to fetch comments for each issue/PR separately.")

    return comments
