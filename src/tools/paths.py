from fnmatch import fnmatch
from pathlib import Path
from src.config.config import get_work_dir
BLOCKED_PATH_PATTERNS = [ # These are the paths we don't want our agent's read or write
    ".env",
    ".env.*"
    ".pem",
    ".key",
    ".secret",
    ".git",
    ".git/**",
    "*.log",
    "*.p12"
]
def normalize_path(path: str) -> str:
    # When ever a particular path is passed to the agent we normalize the path
    normalized = Path(path).as_posix() # This as_posix() converts the path to the forward slash "/"
    # so if the 'path' has "\" backward slash we convert it to forward slash

    if normalized.startswith("./"): # If the path has ./ as prefix we retrieve the path after that prefix
        normalized = normalized[2:]
    return normalized

def is_blocked_path(path: str) -> bool:
    # When ever the agent got any task to work on any file path we first check if the given path is allowed to work
    normalized = normalize_path(path) # we get the normalized path
    return any(fnmatch(normalized, pattern) for pattern in BLOCKED_PATH_PATTERNS) # and checking if the path has any blocked path patterns if yes return 'True'

def resolve_work_path(path: str) -> Path:
    # When the agent wants to create/edit files and put it some folder as part of the changes
    # it has to go into working directory we defined in the config

    work_dir = get_work_dir()
    work_dir.mkdir(parents=True, exist_ok=True) # For a given path object if a directory not exists we create or else its ok

    candidate = (work_dir / path).resolve() # So inside the working directory , we put the path that is passed and create a path.
    try:
        candidate.relative_to(work_dir) # We are checking if the candidate path is a relative path or the path that is present in the working directory or not
    except ValueError as e:
        raise ValueError(f"Path escapes working directory") # if the path that the agent is trying to create is outside the working directory we return valueError
    return candidate