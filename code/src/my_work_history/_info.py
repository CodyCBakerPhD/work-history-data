import os
import re

import requests


def fetch_info_for_date(date: str, username: str) -> list[dict]:
    """
    Fetch GitHub info (issues, PRs, etc.) created by a specific user on a specific date.

    Parameters
    ----------
    date : str
        The date for which to fetch GitHub info, in ISO format (e.g., "2026-01-01").
    username : str
        The GitHub username for which to fetch info.

    Returns
    -------
    list[dict]
        A list of dictionaries containing the GitHub info for the specified date and user.
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

    date_entity = date.replace("-", "+")
    entities_to_url_and_query = {
        f"type-issues_date-{date_entity}": {
            "url": "https://api.github.com/search/issues",
            "query": f"author:{username} type:issue created:{date}T00:00:00..{date}T23:59:59",
        },
        f"type-prs_date-{date_entity}": {
            "url": "https://api.github.com/search/issues",
            "query": f"author:{username} type:pr created:{date}T00:00:00..{date}T23:59:59",
        },
    }
    entities_to_info = dict()
    for entities in entities_to_url_and_query.keys():
        url, query = entities_to_url_and_query[entities]["url"], entities_to_url_and_query[entities]["query"]

        response = requests.get(url=url, headers={"Bearer": f"token {github_token}"}, params={"q": query})

        if response.status_code != 200:
            message = (
                f"GitHub API query `{query}` to URL `{url}` failed!\n"
                f"Status code {response.status_code}: {response.json()}"
            )
            raise RuntimeError(message)

        entities_to_info[entities] = response.json()

    return entities_to_info
