import json
import re
from typing import Any, Callable
from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain.messages import ToolMessage
from langgraph.types import Command

from src.tools.paths import resolve_work_path, is_blocked_path

_FILE_TOOLS = {"read_file", "write_file", "edit_file", "list_files"} # These are the available file tools

BLOCKED_EDIT_PATTERNS = ( # These are the set of blocked edit patterns
    r"\bos\.system\s*\(",
    r"\bsubprocess\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"__import__\s*\(",
)


def _tool_message(request: ToolCallRequest, reason: str) -> ToolMessage:
    return ToolMessage(
        content=reason,
        tool_call_id=request.tool_call["id"],
        name=request.tool_call["name"],
    )


def deny_reason(tool_name: str, arguments: dict[str, Any]) -> str | None:
    """
    Return a denial message or None if the call may proceed.

    """
    if tool_name == "run_command":
        return None

    if tool_name not in _FILE_TOOLS: # if the tool_name is not of the _FILE_TOOLS we return None and don't deny
        return None

    path = arguments.get("path", ".") # For all the file related operations we have path

    if is_blocked_path(str(path)): # Now we check if the path used for the tool input is blocked or not
        return (
            f"Blocked by middleware: access to protected path {path} is not allowed."
        )

    if tool_name == "read_file": # if the tool is read_file ,we try to resolve or check if the path is within the working directory
        try:
            file_path = resolve_work_path(str(path))
        except ValueError as e:
            return f"Blocked by middleware: {e}"

        if file_path.is_file() and file_path.stat().st_size > 1024 * 1024 * 10:  # 10MB , # we check if the file is within certain limit before reading it
            return (
                f"Blocked by middleware: file {file_path} is too large to read."
            )

    payload = ""
    if tool_name == "edit_file":
        payload = str(arguments.get("new_str", ""))
    elif tool_name == "write_file":
        payload = str(arguments.get("content", ""))

    if payload: # if the tool is either write or edit has a payload and if the payload has any blocked patterns then also we deny
        for pattern in BLOCKED_EDIT_PATTERNS:
            if re.search(pattern, payload):
                return (
                    f"Blocked by middleware: suspicious payload contains {pattern!r}."
                )

    return None


class ProtectionMiddleware(AgentMiddleware):
    """Short circuit tool calls that target secret or dangerous payloads."""

    def wrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        name = request.tool_call.get("name", "")
        arguments = request.tool_call.get("args", {})

        reason = deny_reason(name, arguments)

        if reason is not None:
            return _tool_message(request, reason)
        return handler(request)  # continue with the tool call
