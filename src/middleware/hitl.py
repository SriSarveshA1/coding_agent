from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse


def build_hitl_middleware() -> HumanInTheLoopMiddleware: # We return this HumanInTheLoopMiddleware instance that can be injected anywhere
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "read_file": False, # no hitl for read_file tool
            "list_files": False, # no hitl for list_files tool
            "list_jobs": False,
            "stop_job":False,
            "run_command": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "Run a bash command in the current working directory (host machine not a sandbox)"
            },
            "write_file": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "Write or overwrite a file on disk"
            },
            "edit_file": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "Edit an existing file on the disk"
            }
        },
        description_prefix="Coding agent needs your approval to move ahead"
    )