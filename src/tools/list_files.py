import json
import os
from pathlib import Path
from langchain.tools import tool

from src.config.config import get_work_dir
from src.tools.paths import resolve_work_path


@tool
def list_files(path: str = ".") -> str:
    """
    List files and directories under a given path in the working directory.

    Args:
        path: Relative directory to list. Default to the working-dorectory root.
    """

    work_dir = get_work_dir() # Get the working directory path

    try:
        base_path = resolve_work_path(path)# We are checking if the path given to read is a valid path inside the working directory -> workspace or not
        # We pass the 'relative path' of the file and the 'resolve_work_path' gives the path which is of the working directory
    except ValueError as err:
        return json.dumps({"error": f"Path escapes working directory: {err}"})

    if not base_path.exists():
        return json.dumps({"error": f"Path {path!r} does not exist"})
    if not base_path.is_dir():
        return json.dumps({"error": f"Path {path!r} is not a directory"})

    result: list[str] = []


    for root, dirs, files in os.walk(base_path): # We are walking in to the base_path, and this os.walk() walks in to this path recursively and
        # gets the files, directories in that path.
        root_path = Path(root)
        rel_root = root_path.relative_to(work_dir) # Get the relative path to the working directory

        for dir_name in sorted(dirs):
            result.append(f"{(rel_root / dir_name).as_posix()}/")
        for file_name in sorted(files):
            result.append(f"{(rel_root / file_name).as_posix()}")


    return json.dumps(result)
