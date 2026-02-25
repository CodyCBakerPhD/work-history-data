"""Main script to fetch all GitHub activity for a user."""

import gzip
import json
import os
import pathlib
from datetime import datetime

from github_fetchers import (
    fetch_commits,
    fetch_discussions,
    fetch_issue_comments,
    fetch_issues,
    fetch_pull_requests,
    fetch_reviews,
)


def save_data(data: list[dict], category: str, output_dir: pathlib.Path, compress: bool = True) -> None:
    """
    Save fetched data to a JSON file.

    Parameters
    ----------
    data : list[dict]
        Data to save
    category : str
        Category name (e.g., 'issues', 'pull_requests')
    output_dir : pathlib.Path
        Directory to save the file
    compress : bool, optional
        Whether to gzip compress the output (default: True)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"{category}_{timestamp}.json"

    if compress:
        filename += ".gz"
        filepath = output_dir / filename
        with gzip.open(filepath, "wt", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        filepath = output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    print(f"Saved {len(data)} items to {filepath}")


def fetch_all_activity(
    token: str,
    username: str,
    output_dir: pathlib.Path,
    compress: bool = True,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """
    Fetch all GitHub activity for a user.

    Parameters
    ----------
    token : str
        GitHub personal access token
    username : str
        GitHub username
    output_dir : pathlib.Path
        Directory to save output files
    compress : bool, optional
        Whether to gzip compress output files (default: True)
    start_date : str, optional
        ISO 8601 format date (YYYY-MM-DD) to filter from
    end_date : str, optional
        ISO 8601 format date (YYYY-MM-DD) to filter to

    Returns
    -------
    dict
        Summary of fetched data
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "username": username,
        "fetch_timestamp": datetime.now().isoformat(),
        "date_range": {"start": start_date, "end": end_date},
        "categories": {},
    }

    # Fetch issues
    print("\n" + "=" * 80)
    print("FETCHING ISSUES")
    print("=" * 80)
    issues = fetch_issues(token, username, start_date, end_date)
    save_data(issues, "issues", output_dir, compress)
    summary["categories"]["issues"] = len(issues)

    # Fetch pull requests
    print("\n" + "=" * 80)
    print("FETCHING PULL REQUESTS")
    print("=" * 80)
    pull_requests = fetch_pull_requests(token, username, start_date, end_date)
    save_data(pull_requests, "pull_requests", output_dir, compress)
    summary["categories"]["pull_requests"] = len(pull_requests)

    # Fetch issue comments
    print("\n" + "=" * 80)
    print("FETCHING ISSUE/PR COMMENTS")
    print("=" * 80)
    issue_comments = fetch_issue_comments(token, username, start_date, end_date)
    save_data(issue_comments, "issue_comments", output_dir, compress)
    summary["categories"]["issue_comments"] = len(issue_comments)

    # Fetch discussions
    print("\n" + "=" * 80)
    print("FETCHING DISCUSSIONS")
    print("=" * 80)
    discussions = fetch_discussions(token, username, start_date, end_date)
    save_data(discussions, "discussions", output_dir, compress)
    summary["categories"]["discussions"] = len(discussions)

    # Fetch commits
    print("\n" + "=" * 80)
    print("FETCHING COMMITS")
    print("=" * 80)
    commits = fetch_commits(token, username, start_date, end_date)
    save_data(commits, "commits", output_dir, compress)
    summary["categories"]["commits"] = len(commits)

    # Fetch reviews
    print("\n" + "=" * 80)
    print("FETCHING PR REVIEWS")
    print("=" * 80)
    reviews = fetch_reviews(token, username, start_date, end_date)
    save_data(reviews, "reviews", output_dir, compress)
    summary["categories"]["reviews"] = len(reviews)

    # Save summary
    timestamp = datetime.now().strftime("%Y-%m-%d")
    summary_path = output_dir / f"summary_{timestamp}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 80)
    print("FETCH COMPLETE")
    print("=" * 80)
    print(f"Summary saved to {summary_path}")

    return summary


def main(start_date: str, end_date: str, compress: bool, output_dir: pathlib.Path) -> None:
    """
    Main entry point.

    Parameters
    ----------
    start_date : str
        ISO 8601 format date (YYYY-MM-DD) to filter from.
        Example: "2026-01-01"
    end_date : str
        ISO 8601 format date (YYYY-MM-DD) to filter to.
        Example: "2026-02-01"
    compress : bool, default: False
        Whether to gzip compress output files.
    output_dir : pathlib.Path
        Directory to save output files.

    Configure date ranges and settings by editing the variables below.
    """
    # Get GitHub token from environment variable
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError(
            "GITHUB_TOKEN environment variable not set. " "Please set it with: export GITHUB_TOKEN=your_token_here"
        )

    # Get username from environment variable
    username = os.environ.get("GITHUB_USERNAME")
    if not username:
        raise ValueError(
            "GITHUB_USERNAME environment variable not set. " "Please set it with: export GITHUB_USERNAME=your_username"
        )

    # Set output directory
    print(f"Fetching GitHub activity for user: {username}")
    if start_date or end_date:
        print(f"Date range: {start_date or 'start'} to {end_date or 'now'}")
    print(f"Output directory: {output_dir}")

    # Fetch all activity
    summary = fetch_all_activity(
        token,
        username,
        output_dir,
        compress=compress,
        start_date=start_date,
        end_date=end_date,
    )

    # Print summary
    print("\nFetch Summary:")
    for category, count in summary["categories"].items():
        print(f"  {category}: {count}")


if __name__ == "__main__":
    repo_head = pathlib.Path(__file__).parent.parent

    start_date = "2026-01-01"
    end_date = "2026-01-04"
    output_dir = repo_head / "sourcedata" / "2026-01"

    main(
        start_date=start_date,
        end_date=end_date,
        compress=False,
        output_dir=output_dir,
    )
