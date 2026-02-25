"""Fetch all commits by a GitHub user."""

from typing import Any

from .base import GitHubFetcher


def fetch_commits(token: str, username: str, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch all commits by the user across all repositories.

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
        List of all commits by the user
    """
    fetcher = GitHubFetcher(token, username, start_date, end_date)

    date_range_str = ""
    if start_date or end_date:
        date_range_str = f" (date range: {start_date or 'start'} to {end_date or 'now'})"
    print(f"Fetching commits by {username}{date_range_str}...")

    # Use GitHub search API to find all commits by the user
    url = f"{fetcher.base_url}/search/commits"
    # Note: commits use 'committer-date' for date filtering, not 'created'
    date_query = ""
    if start_date or end_date:
        date_parts = []
        if start_date:
            date_parts.append(f">={start_date}")
        if end_date:
            date_parts.append(f"<={end_date}")
        date_query = f" committer-date:{''.join(date_parts)}"

    query = f"author:{username}{date_query}"
    params = {"q": query, "sort": "committer-date", "order": "desc"}

    # Commits search requires a special accept header
    fetcher.session.headers["Accept"] = "application/vnd.github.cloak-preview+json"

    commits = fetcher.search_paginated(url, params)

    # Restore default accept header
    fetcher.session.headers["Accept"] = "application/vnd.github+json"

    print(f"Total commits fetched: {len(commits)}")
    return commits
