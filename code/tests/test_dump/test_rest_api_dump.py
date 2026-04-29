import importlib.metadata
import json
import pathlib

import my_work_history
import pytest

pytestmark = pytest.mark.ai_generated


def test_dump_info_for_date_rest(tmp_path: pathlib.Path) -> None:
    version = importlib.metadata.distribution("my_work_history").version
    major, minor, _ = version.split(".")
    username = "codycbakerphd"

    test_directory = tmp_path / "test_dump"
    test_directory.mkdir(exist_ok=True)
    test_version_directory = test_directory / f"version-{major}+{minor}"
    test_request_directory = test_version_directory / f"username-{username}" / "request-rest"

    expected_directory = pathlib.Path(__file__).parent / "expected_dumps"
    expected_version_directory = expected_directory / "version-0+1"  # Use static version since assertions are relative
    expected_request_directory = expected_version_directory / f"username-{username}" / "request-rest"

    my_work_history.dump_info_for_date(
        directory=test_directory,
        date="2026-01-05",
        username=username,
        request_type="rest",
    )

    test_file_paths = sorted(list(test_request_directory.rglob(pattern="*.json")))
    relative_test_file_paths = {path.relative_to(test_version_directory) for path in test_file_paths}
    expected_file_paths = sorted(list((expected_request_directory.rglob(pattern="*.json"))))
    relative_expected_file_paths = {path.relative_to(expected_version_directory) for path in expected_file_paths}
    assert relative_test_file_paths == relative_expected_file_paths

    for test_file_path, expected_file_path in zip(test_file_paths, expected_file_paths):
        with test_file_path.open(mode="r") as file_stream:
            test_content = json.load(file_stream)
        with expected_file_path.open(mode="r") as file_stream:
            expected_content = json.load(file_stream)
        assert test_content == expected_content
