from langchain.tools import tool

from src.tools.paths import resolve_work_path
from src.tools.text import prepare_file_content


@tool
def edit_file(path: str, old_str: str, new_str: str) -> str:
    """

    Replace `old_str` with `new_str` in the file at `path`.

    Language agnostic: .js, .java, .py and other text files all use exact substring replace.
    Pass an empty `old_str` to create new file(same as `write_file`).
    Both strings must use real newlines, and not the two-character sequence backslash-n.

    Args:
        path: Relative path of the file to edit (e.g. "README.md")
        old_str: Exact text to replace. Empty string creates new file.
        new_str: Exact text to replace with.

    """

    if not path or old_str == new_str:
        return "Error: Invalid input"

    # Trying to remove unwanted characters in both the old_str,new_str by checking the path's suffix
    old_str = prepare_file_content(path, old_str)
    new_str = prepare_file_content(path, new_str)

    try:
        file_path = resolve_work_path(path) # Checking if the given path is within the working directory
    except ValueError as err:
        return f"Error: Path escapes working directory: {err}"

    if old_str == "": # if the old_str=="" then we can just write the entire new_str into the file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(new_str, encoding="utf-8")
        return f"Created new file {path!r}"

    try:
        old_content = file_path.read_text(encoding="utf-8") # If the old_str has some value, then we read the content of this file_path
    except Exception as err:
        return f"Error: Failed to read file {path!r}: {err}"

    if old_str not in old_content: # Then we are checking the formatted old_str is present in the already inserted old_content
        return f"Error: {path!r} does not contain {old_str!r}"

    new_content = old_content.replace(old_str, new_str) # Then we are trying to replace and insert it
    file_path.write_text(new_content, encoding="utf-8")
    return f"Replaced {old_str!r} with {new_str!r} in {path!r}"