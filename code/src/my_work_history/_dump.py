import importlib.metadata
import json
import pathlib
import typing

from ._fetch_info import fetch_info_for_date
from ._globals import INFO_TYPES


def dump_specific_info(
    directory: pathlib.Path,
    info_type: typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"],
    date: str,
    username: str,
    request_type: typing.Literal["rest", "graphql"] = "rest",
) -> bool:
    """
    Parameters
    ----------
    directory : pathlib.Path
        The base directory to save the data to.
    info_type : typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"]
        The type of information to fetch and save.
    date : str
        The date to fetch information for, in the format "YYYY-MM-DD".
    username : str
        The GitHub username to fetch information about.
    request_type : typing.Literal["rest", "graphql"]
        The type of API request to use when fetching information (e.g., "rest" or "graphql").

    Returns
    -------
    bool
        Whether or not the GitHub API rate limit was hit during the query.
    """
    year, month, day = date.split("-")
    version = importlib.metadata.distribution("my_work_history").version
    major, minor, _ = version.split(".")

    subdir = (
        directory
        / f"version-{major}+{minor}_request-{request_type}"
        / f"username-{username}"
        / f"year-{year}"
        / f"month-{month}"
        / f"day-{day}"
    )
    subdir.mkdir(parents=True, exist_ok=True)

    filename = f'info-{info_type.replace("_", "+")}_date-{date.replace("-", "+")}.json'
    file_path = subdir / filename
    if file_path.exists():
        return False

    info, hit_rate_limit = fetch_info_for_date(
        info_type=info_type, date=date, username=username, request_type=request_type
    )

    if hit_rate_limit:
        return hit_rate_limit
    if request_type == "rest" and info["total_count"] == 0:
        return False
    if request_type == "graphql" and len(info) == 0:
        a = 1
        a
        return False

    with file_path.open(mode="w") as file_stream:
        json.dump(obj=info, fp=file_stream, indent=1)

    return False


def dump_info_for_date(
    directory: pathlib.Path, date: str, username: str, request_type: typing.Literal["rest", "graphql"] = "rest"
) -> None:
    for info_type in INFO_TYPES:
        hit_rate_limit = dump_specific_info(
            directory=directory, info_type=info_type, date=date, username=username, request_type=request_type
        )
        if hit_rate_limit:
            break
