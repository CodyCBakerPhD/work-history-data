import datetime
import pathlib
import typing

from ._dump import dump_info_for_date


def update(
    directory: pathlib.Path,
    username: str,
    past_number_of_days: int,
    request_type: typing.Literal["rest", "graphql"],
) -> None:
    today = datetime.date.today()

    date = today.strftime("%Y-%m-%d")
    dump_info_for_date(directory=directory, date=date, username=username, request_type=request_type, overwrite=True)
    date = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    dump_info_for_date(directory=directory, date=date, username=username, request_type=request_type, overwrite=True)
    for day in range(2, past_number_of_days + 1):
        date = (today - datetime.timedelta(days=day)).strftime("%Y-%m-%d")
        dump_info_for_date(
            directory=directory, date=date, username=username, request_type=request_type, overwrite=False
        )
