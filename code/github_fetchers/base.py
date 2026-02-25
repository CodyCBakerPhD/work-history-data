"""Base utilities for GitHub API fetching with rate limiting and pagination."""

import time
from typing import Any

import requests


class GitHubFetcher:
    """Base class for GitHub API fetching with common utilities."""

    def __init__(self, token: str, username: str, start_date: str | None = None, end_date: str | None = None):
        """
        Initialize the GitHub fetcher.

        Parameters
        ----------
        token : str
            GitHub personal access token
        username : str
            GitHub username to fetch data for
        start_date : str, optional
            ISO 8601 format date (YYYY-MM-DD) to filter results from (inclusive)
        end_date : str, optional
            ISO 8601 format date (YYYY-MM-DD) to filter results to (inclusive)
        """
        self.token = token
        self.username = username
        self.start_date = start_date
        self.end_date = end_date
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Bearer": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _build_date_range_query(self) -> str:
        """Build date range query string for GitHub search."""
        if not self.start_date and not self.end_date:
            return ""

        date_parts = []
        if self.start_date:
            date_parts.append(f">={self.start_date}")
        if self.end_date:
            date_parts.append(f"<={self.end_date}")

        return f" created:{''.join(date_parts)}"

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Check rate limit and sleep if necessary."""
        remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        if remaining < 10:
            reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
            sleep_time = max(reset_time - time.time(), 0) + 1
            print(f"Rate limit approaching. Sleeping for {sleep_time:.0f} seconds...")
            time.sleep(sleep_time)

    def fetch_paginated(
        self, url: str, params: dict[str, Any] | None = None, max_pages: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch all pages of results from a GitHub API endpoint.

        Parameters
        ----------
        url : str
            API endpoint URL
        params : dict, optional
            Query parameters
        max_pages : int, optional
            Maximum number of pages to fetch (None for all pages)

        Returns
        -------
        list[dict]
            All items from all pages
        """
        if params is None:
            params = {}

        params.setdefault("per_page", 100)
        params.setdefault("page", 1)

        all_items = []
        page_count = 0

        while True:
            if max_pages and page_count >= max_pages:
                break

            response = self.session.get(url, params=params)
            response.raise_for_status()

            self._handle_rate_limit(response)

            items = response.json()
            if not items:
                break

            all_items.extend(items)
            page_count += 1

            print(f"Fetched page {page_count}: {len(items)} items (total: {len(all_items)})")

            # Check if there's a next page
            if "next" not in response.links:
                break

            params["page"] += 1

        return all_items

    def search_paginated(
        self, url: str, params: dict[str, Any] | None = None, max_pages: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch paginated search results from GitHub API.

        Search endpoints return results in a different format with 'items' key.

        Parameters
        ----------
        url : str
            API endpoint URL
        params : dict, optional
            Query parameters
        max_pages : int, optional
            Maximum number of pages to fetch (None for all pages)

        Returns
        -------
        list[dict]
            All items from all pages
        """
        if params is None:
            params = {}

        params.setdefault("per_page", 100)
        params.setdefault("page", 1)

        all_items = []
        page_count = 0

        while True:
            if max_pages and page_count >= max_pages:
                break

            response = self.session.get(url, params=params)
            response.raise_for_status()

            self._handle_rate_limit(response)

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            all_items.extend(items)
            page_count += 1

            total_count = data.get("total_count", 0)
            print(f"Fetched page {page_count}: {len(items)} items (total: {len(all_items)}/{total_count})")

            # Check if there's a next page
            if "next" not in response.links:
                break

            params["page"] += 1

        return all_items
