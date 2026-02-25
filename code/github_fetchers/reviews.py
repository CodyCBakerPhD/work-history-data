"""Fetch all pull request reviews by a GitHub user."""

from typing import Any

from .base import GitHubFetcher


def fetch_reviews(token: str, username: str, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch all pull request reviews submitted by the user.

    Note: GitHub's search API doesn't directly support searching for reviews.
    This function searches for PRs where the user was a reviewer.

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
        List of pull requests where the user submitted reviews
    """
    fetcher = GitHubFetcher(token, username, start_date, end_date)

    date_range_str = ""
    if start_date or end_date:
        date_range_str = f" (date range: {start_date or 'start'} to {end_date or 'now'})"
    print(f"Fetching pull request reviews by {username}{date_range_str}...")

    # Use GitHub search API to find PRs reviewed by the user
    url = f"{fetcher.base_url}/search/issues"
    query = f"reviewed-by:{username} type:pr{fetcher._build_date_range_query()}"
    params = {"q": query, "sort": "created", "order": "desc"}

    reviewed_prs = fetcher.search_paginated(url, params)

    print(f"Total PRs reviewed: {len(reviewed_prs)}")
    print("Note: This returns PRs where you submitted reviews, not individual review comments.")
    print("For detailed review data, fetch reviews for each PR separately using the PR API.")

    return reviewed_prs
