import hashlib

import requests
import datetime
import os
import hashlib

def fetch_info(start_date: str, end_date: str, username: str) -> list[dict]:
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "Please set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token."
        raise ValueError(message)

    # TODO: does this have to be full ISO?
    start = datetime.datetime.fromisoformat(start_date)
    end = datetime.datetime.fromisoformat(end_date)

    start_iso = start.isoformat()
    end_iso = end.isoformat()

    url_to_query = {
        "https://api.github.com/search/issues": f"author:{username} type:issue created:{start_iso}..{end_iso}"
    }
    query_hash_to_info = dict()
    for url, query in url_to_query.items():
        response = requests.get(
            url,
            headers={"Bearer": f"token {github_token}"},
            params={"q": query}
        )

        if response.status_code != 200:
            message = (
                f"GitHub API query `{query}` to URL `{url}` failed!\nStatus code {response.status_code}: {response.json()}"
            )
            raise RuntimeError(message)

        hash = hashlib.sha1("".join([url, query]).encode()).hexdigest()
        query_hash_to_info[hash] = response.json()

    return query_hash_to_info
