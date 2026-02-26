import datetime
import pathlib

import rich_click

import my_work_history


# mywork
@rich_click.group(name="mywork")
def _mywork_cli():
    pass


# mywork update
@_mywork_cli.command(name="update")
@rich_click.option("--directory", type=str, default=".", help="Directory to save the data to.")
@rich_click.option("--username", type=str, help="GitHub username to fetch information about.")
@rich_click.option(
    "--recency", type=int, default=None, help="Number of most recent days to fetch. Smart updating still applies."
)
def _mywork_update_cli(directory: str, username: str, recency: int | None = None):
    directory = pathlib.Path(directory)
    today = datetime.date.today()

    MAX_RECENCY = 365 * 20
    days_to_fetch = min(recency, MAX_RECENCY) if recency is not None else recency
    for day in range(1, days_to_fetch + 1):
        date = today - datetime.timedelta(days=day)
        my_work_history.dump_info_for_date(directory=directory, date=date, username="codycbakerphd")
