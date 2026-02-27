import datetime
import pathlib
import typing

import rich_click

import my_work_history


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
    default=None,
    help="Number of most recent days to fetch. Smart updating still applies.",
)
@rich_click.option(
    "--request",
    "request_type",
    type=rich_click.Choice(["rest", "graphql"], case_sensitive=False),
    default="rest",
    help="The type of API request to use when fetching information (e.g., 'rest' or 'graphql').",
)
def _mywork_update_cli(
    directory: str,
    username: str,
    past_number_of_days: int | None = None,
    request_type: typing.Literal["rest", "graphql"] = "rest",
) -> None:
    directory = pathlib.Path(directory)
    today = datetime.date.today()

    MAX_RECENCY = 365 * 20
    days_to_fetch = min(past_number_of_days, MAX_RECENCY) if past_number_of_days is not None else past_number_of_days
    for day in range(1, days_to_fetch + 1):
        date = (today - datetime.timedelta(days=day)).strftime("%Y-%m-%d")
        my_work_history.dump_info_for_date(directory=directory, date=date, username=username, request_type=request_type)
