import datetime
import pathlib
import typing

import tqdm

from ._dump import dump_info_for_date


def update(
    directory: pathlib.Path,
    username: str,
    past_number_of_days: int,
    request_type: typing.Literal["rest", "graphql"],
) -> None:
    today = datetime.date.today()

    with tqdm.tqdm(
        iterable=range(past_number_of_days + 1),
        desc="Fetching work history",
        unit="days",
        dynamic_ncols=True,
    ) as progress_bar:
        for day in progress_bar:
            date = (today - datetime.timedelta(days=day)).strftime("%Y-%m-%d")
            progress_bar.set_postfix(date=date)
            overwrite = day < 2
            dump_info_for_date(
                directory=directory, date=date, username=username, request_type=request_type, overwrite=overwrite
            )
