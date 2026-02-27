import importlib.metadata
import json
import pathlib

import my_work_history
import py


def test_dump_info_for_date_rest(tmp_path: py.local.path) -> None:
    version = importlib.metadata.distribution("my_work_history").version
    major, minor, _ = version.split(".")

    test_directory = pathlib.Path(tmp_path) / "test_dump"
    test_directory.mkdir(exist_ok=True)
    test_version_directory = test_directory / f"version-{major}+{minor}_request-rest"

    expected_directory = pathlib.Path(__file__).parent / "expected_rest_dump"
    expected_version_directory = (
        expected_directory / "version-0+1_request-rest"  # Use static version since assertions are relative
    )

    my_work_history.dump_info_for_date(
        directory=test_directory,
        date="2026-01-05",
        username="codycbakerphd",
    )

    test_file_paths = sorted(list(test_directory.rglob(pattern="*.json")))
    relative_test_file_paths = {path.relative_to(other=test_version_directory) for path in test_file_paths}
    expected_file_paths = sorted(list((expected_directory.rglob(pattern="*.json"))))
    relative_expected_file_paths = {path.relative_to(other=expected_version_directory) for path in expected_file_paths}
    assert relative_test_file_paths == relative_expected_file_paths

    for test_file_path, expected_file_path in zip(test_file_paths, expected_file_paths):
        with test_file_path.open(mode="r") as file_stream:
            test_content = json.load(file_stream)
        with expected_file_path.open(mode="r") as file_stream:
            expected_content = json.load(file_stream)
        assert test_content == expected_content
