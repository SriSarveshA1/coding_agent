
import json
from datetime import datetime, UTC
from typing import Callable, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_protocol import Command
from langgraph.prebuilt.tool_node import ToolCallRequest

from src.config.config import get_work_dir


class AuditMiddleware(AgentMiddleware):
    """Append a JSON record after each tool call (allowed or denied)"""


    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command], # Callable function's parameter will have ToolCallRequest and the response can have
                                                                    # either ToolMessage | Command
    ) -> ToolMessage | Command:
        result = handler(request)  # make the tool call first, and log after the tool is completed
        preview = ""
        if isinstance(result, ToolMessage):
            preview = str(result.content)[:200] # We are only logging 200 characters for simplicity
        self._write({
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": request.tool_call.get("name"),
            "result_preview": preview,
            "arguments": request.tool_call.get("args"),
        })
        return result

    def _write(
            self,
            entry: dict[str, Any]
    ) -> None:
        log_path = get_work_dir() / ".agent_audit.log" # we try to append the working directory with the log file path
        log_path.parent.mkdir(parents=True, exist_ok=True) # if the log files parent directory is not there we create it
        with log_path.open("a", encoding="utf-8") as f: # This also creates the file in the path if it's not already there
            f.write(json.dumps(entry) + "\n") # We do write of the json dump of the log into the file