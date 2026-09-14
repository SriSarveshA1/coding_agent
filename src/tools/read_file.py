from langchain.tools import tool
from src.tools.paths import resolve_work_path


@tool
def read_file(path: str) -> str:
    """
    Reads a UTF-8 text file from the working directory.

    Args:
        path: Relative path of the file, e.g. 'src/App.js' or 'README.md' or 'data/example.json'
    """

    try:
        file_path = resolve_work_path(path) # We are checking if the path given to read is a valid path inside the working directory -> workspace or not
        # We pass the 'relative path' of the file and the 'resolve_work_path' gives the path which is based on the working directory

        print('Resolved working directory file_path: ',file_path) # Will append the given file path to the workspace directory and read the content of that path
    except ValueError as err:
        return f"Path escapes working directory: {err}"

    try:
        return file_path.read_text(encoding="utf-8") # go and read the file and return the content
    except FileNotFoundError:
        return f"File not found: {path}"
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as err:
        return f"Error reading file: {err}"