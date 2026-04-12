import pathlib
import typing

import rich_click

from ._create_project import create_project_page
from ._minify import _minify
from ._update import update


# mywork
@rich_click.group(name="mywork")
def _mywork_cli():
    pass


# mywork update
@_mywork_cli.command(name="update")
@rich_click.option("--directory", type=str, required=True, help="Directory to save the data to.")
@rich_click.option("--username", type=str, required=True, help="GitHub username to fetch information about.")
@rich_click.option(
    "--recency",
    "past_number_of_days",
    type=int,
    required=True,
    help="Number of most recent days to fetch. Smart updating still applies.",
)
@rich_click.option(
    "--request",
    "request_type",
    type=rich_click.Choice(["rest", "graphql"], case_sensitive=False),
    required=True,
    help="The type of API request to use when fetching information (e.g., 'rest' or 'graphql').",
)
def _mywork_update_cli(
    directory: str,
    username: str,
    past_number_of_days: int,
    request_type: typing.Literal["rest", "graphql"],
) -> None:
    directory = pathlib.Path(directory)

    update(directory=directory, username=username, past_number_of_days=past_number_of_days, request_type=request_type)


# mywork minify
@_mywork_cli.command(name="minify")
@rich_click.option(
    "--directory",
    type=str,
    required=True,
    help=(
        "The specific subdirectory to minify; should be for a specific version, username, and request type. "
        "E.g., `/path/to/version-0+1/username-codycbakerphd/request-graphql`."
    ),
)
def _mywork_minify_cli(directory: str) -> None:
    directory = pathlib.Path(directory)

    _minify(directory=directory)


# mywork create-project
@_mywork_cli.command(name="create-project")
@rich_click.option("--owner", type=str, required=True, help="GitHub user or organization login to own the project.")
@rich_click.option("--title", type=str, required=True, help="Title of the new GitHub Project.")
def _mywork_create_project_cli(owner: str, title: str) -> None:
    project = create_project_page(owner=owner, title=title)
    if project:
        print(f"Project created successfully!\nID: {project['id']}\nURL: {project['url']}")
