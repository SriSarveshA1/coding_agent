import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# This resolve() helps converting the path to the absolute path(if the path passed has any ..(relative path)), and the .parent gets the immediate parent folder path

# We store the other set of directory paths of folders parallel to src
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DEFAULT_WORK_DIR = PROJECT_ROOT / "workspace" # this is the working directory for the agent's to dump its results and codes that it do

AGENT_NAME = "Sarvesh_Coding_Agent"

MAX_MODEL_CALLS_PER_RUN = int(os.getenv("MAX_MODEL_CALLS_PER_RUN", "10"))
MAX_READ_BYTES = int(os.getenv("MAX_READ_BYTES", "1000000"))

def hitl_enabled() -> bool:
    return os.getenv("HITL_ENABLED", "true").lower() in {"1", "true", "yes"}

def get_work_dir() -> Path:
    override = os.getenv("WORK_DIR", "").strip()
    if override:
        # This expanduser() helps in converting the ~ symbol to the current user's home directory
        return Path(override).expanduser().resolve() # ~/Developer/workspce => /Users/john/Developer/workspce

    return DEFAULT_WORK_DIR.resolve()