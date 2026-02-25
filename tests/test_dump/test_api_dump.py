import pathlib

import my_work_history
import py


def test_fetch_info(tmp_path: py.local.path) -> None:
    output_directory = pathlib.Path(tmp_path) / "test_dump"
    output_directory.mkdir(exist_ok=True)

    expected_output_directory = pathlib.Path(__file__).parent / "expected_dump"
    expected_output_directory

    test_info = my_work_history.dump_info_for_date(
        date="2026-01-05",
        username="codycbakerphd",
        output_directory=output_directory,
    )
    expected_info = {}
    assert test_info == expected_info
