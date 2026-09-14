from src.tools.edit_file import edit_file
from src.tools.list_files import list_files
from src.tools.read_file import read_file
from src.tools.write_file import write_file

ALL_TOOLS = [
    write_file,
    edit_file,
    read_file,
    list_files,
]


def tool_catalog() -> list[dict[str, str]]:
    """Name + Description for all tools"""
    return [{"name": tool.name, "description": tool.description} for tool in ALL_TOOLS]