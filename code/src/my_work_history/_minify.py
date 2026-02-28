import gzip
import json
import pathlib


def _minify(directory: pathlib.Path) -> None:
    if directory.parts[-1] != "request-graphql":
        message = (
            f"Directory name `{directory.name}` at `{directory}` does not appear to be GraphQL-based! "
            "Other types are not yet supported."
        )
        raise NotImplementedError(message)

    all_info_file_paths = list(directory.rglob(pattern="*.json"))
    all_info = set()
    for info_file_path in all_info_file_paths:
        with info_file_path.open(mode="r") as file_stream:
            info: list = json.load(file_stream)
        for value in info:
            all_info.add(value)

    minified_info_file_path = directory / "all_info.min.json.gz"
    with gzip.open(filename=minified_info_file_path, mode="wt", encoding="utf-8") as file_stream:
        json.dump(obj=list(all_info), fp=file_stream, indent=0)
