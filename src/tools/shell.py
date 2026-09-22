import os
import re
import shlex
import subprocess
import sys
import time

from langchain_core.tools import tool

from src.config.config import get_work_dir
from src.tools.jobs import now_iso, register, BackgroundJob, read_log_tail, stop_pid, all_jobs, is_alive

# The below variables can be ideally picked from env variables.
MAX_OUTPUT_CHARS = 8000 # This is logs that will be coming up from the command that is running
DEFAULT_TIMEOUT = 30 # Timeout for the command that will be running on the shell

# We can have regex of blocked command patterns which we don't want to run on the shell by the tool triggered by the agent
BLOCKED_COMMAND_PATTERNS = (
    r"\bsudo\b",
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\s*\{",
    r"\bdd\s+if=",
    r"curl\s+[^|]*\|\s*(ba)?sh",
    r"wget\s+[^|]*\|\s*(ba)?sh",
    r"\bchmod\s+777\b",
)

# Below are the commands which would spin up a web server which is a long-running process, which needs to be maintained at background
# So all these commands that are below will be a separate background job that we will be maintaining in the jobs.py 's background jobs list
SERVER_PATTERNS = (
    r"\bflask(\s+--app)?\s+run\b",
    r"\buvicorn\b",
    r"\bgunicorn\b",
    r"\bhypercorn\b",
    r"\bpython[0-9.]*\s+\S*app\.py\b",
    r"\bnpm\s+start\b",
    r"\bnpx\s+(serve|next|vite|nuxt)\b",
    r"\bstreamlit\s+run\b",
)

## Python specific handling patterns:
_PIP_PREFIX = re.compile(  # This holds the regex pattern that matches all the pip based commands
    r"^(?:pip[0-9.]*|python[0-9.]*\s+-m\s+pip)\b",
    re.IGNORECASE,
)
_PYTHON_PREFIX = re.compile(r"^python[0-9.]*\b", re.IGNORECASE) # This holds the regex for python based commands
_FLASK_PREFIX = re.compile(r"^flask\b", re.IGNORECASE) # This holds the regex for the flask based commands


def deny_command(command: str) -> str | None:
    stripped = command.strip()
    if not stripped:
        return "Blocked by middleware: command is empty"

    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, flags=re.IGNORECASE): # We are ignoring the commands case and checking if its matching with any blocked command patterns
            return f"Blocked by middleware: command matched a dangerous pattern {pattern}"

    return None  # the command is safe and can proceed

def looks_like_server(command: str) -> bool:
    # We are iterating over the regex pattern which could spin up a server/long running process , we use this to check and add this as a background job
    return any(re.search(pattern, command, flags=re.IGNORECASE) for pattern in SERVER_PATTERNS)


def rewrite_command(command: str) -> str:
    # sys.executable gives the path in which the particular command is running.
    # Our coding agent is also running in the same virtual environment present in this repo, so sys.executable gives the path to the virtual environment
    # in which the agent is running

    # This shlex.quote will wrap the path in unix specific quote and while wrapping if there are any spaces it will also be included as part of the path

    exe = shlex.quote(sys.executable)

    stripped = command.strip()

    if _PIP_PREFIX.match(stripped): # if the command is of pip command,
        # stripped = pip install flask.py , from this stripped we pick the pattern of pip command and replace it with exe(/venv/bin/python)
        # We are doing $ pip install flask.py --> /venv/bin/python -m pip install flask
        return _PIP_PREFIX.sub(f"{exe} -m pip", stripped, count=1) # .sub is substituting the stripped command's _PIP_PREFIX part with the exe and count =1 ,
                                                                        # does it for the 1st occurence of the match and does the replacement

    if _PYTHON_PREFIX.match(stripped):
        # We are doing $ python app.py  ---> /venv/bin/python app.py
        return _PYTHON_PREFIX.sub(exe, stripped, count=1)

    if _FLASK_PREFIX.match(stripped):
        return _FLASK_PREFIX.sub(f"{exe} -m flask", stripped, count=1)

    return command

def _clip(text: str) -> str:
    # When we want to stip out the text content and get only MAX_OUTPUT_CHARS chars of the text
    if len(text) <= MAX_OUTPUT_CHARS: # if the length of the text is within the max output chars we return the entire thing
        return text

    return text[:MAX_OUTPUT_CHARS] + "\n... (truncated)" # if not we only get those max output chars and attach the truncated text


def _run_forground(command: str, timeout: int) -> str:
    cwd = get_work_dir()
    cwd.mkdir(parents=True, exist_ok=True) # The retrieved working directory of the agent , we are creating the parents folder if not exists
    env = os.environ.copy() # We are getting the copy of all the environmental variables and storing it as a dict
    env.setdefault("PYTHONUNBUFFERED", "1") # This flag makes the python process to send the stdout,stderr logs immediately to the terminal without buffering

    try:
        completed = subprocess.run(
            ["/bin/bash", "-lc", command], # This makes the command run in the bash shell and this -l will load all the init files before running the commands
            cwd=cwd, # We are setting the working directory in which we want to run this command
            env=env, # We are giving the entire environmental variable access which the agent has
            capture_output=True, # This will help us to catch stdout, stderr content, we would like to not print the logs to the agent terminal, we will have them seperately
            text=True, # we will receive the logs as text not as bytes
            timeout=timeout, # we also give a timeout period within which the command has to get executed
        )
    except subprocess.TimeoutExpired as e: # if the command crosses beyond the timeperiod we get this exception
        stdout = (e.stdout or "") + (e.stderr or "") # We combine the stdout and stderr logs in the return message
        return (
            f"Timed out after {timeout}s (process killed)."
            "If this is a server, rerun with background=true." # This kind of string messages will let the agent to pass the run_command with background=true
            f"{_clip(str(stdout))}" # we pick only the max_output_chars
        )

    # command completed successfully, then we land here
    chunks = []
    if completed.stdout:
        chunks.append(completed.stdout.rstrip()) # We are getting the stdout and stripping the space
    if completed.stderr:
        chunks.append(completed.stderr.rstrip()) # we are getting the stderr and stripping the space

    body = "\n".join(chunks) if chunks else "No output." # we are making the chunks as single string if the chunks exists
    return f"exit_code={completed.returncode}\ncwd={cwd}\n_{_clip(body)}" # we are returning the exit_code(from the returncode) with truncated logs(body)


def _run_background(command: str) -> str:
    cwd = get_work_dir()
    cwd.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    # since this is a long-running process we should be maintaining the logs file separate
    log_dir = cwd / ".agent_jobs" # we will be storing in the current working directory
    log_dir.mkdir(parents=True, exist_ok=True) # we will create the parent paths if its not existing

    stamp = now_iso().replace(":", "").replace("+", "") # replacing any special characters in the timestamp, as this is going to get
        # used in the file name

    tmp_log = log_dir / f"pending-{stamp}.log"  # For each job/process that is created based on the timestamp we create a log file
    log_file = tmp_log.open("w", encoding="utf-8") # We open the log file with the write mode

    try:
        proc = subprocess.Popen(
            ["/bin/bash", "-lc", command],
            cwd=cwd,
            env=env,
            stdout=log_file, # We give the log_file reference where all the normal logs gets stored in this file
            stderr=subprocess.STDOUT, # And when there is any error we put that in the stdout only so that the agent can directly read it
            start_new_session=True, # this makes this subprocess detaches from the parent agent process, this makes this subprocess a daemon process
        )
    finally:
        log_file.close() # This log file is closed after the command is triggered , so we store here the logs which are needed
                        # during the process initialisation

    # But the actual process is still running and those process logs we need to store it permanently
    log_path = log_dir / f"{proc.pid}.log" # We are creating a log file path based on the process id
    tmp_log.rename(log_path) # We are renaming the temp log file path with the new permanent log file path

    # Now we are registering the background job with the process that is created
    register(
        BackgroundJob(
            pid=proc.pid,
            command=command,
            log_path=log_path, # This log_path stores logs that are needed during the background job's execution period
            started_at=now_iso(),# New current timestamp when this background job is created
            proc=proc,
        )
    )

    time.sleep(1) # After registering the process in the background we wait for 1 sec and check for the process status
    # whether its running or not , as the process that is started can get terminated immediatly due to some issue

    tail = read_log_tail(log_path) # We fetch the recent tail logs from the log file

    if proc.poll() is not None: # We are polling and checking if the process is still running or not
        stop_pid(proc.pid) # if its not running then we are removing it from the background job
        return (
            f"Background command exitted immediately (pid={proc.pid})."
            f"exit_code={proc.returncode}.\n{_clip(tail)}"
        )

    # if the process is still running
    urls = re.findall(r"https?://[^\s]+", tail) # we check if the process emited logs has any URL's
                                                        # we extract all the url's

    url_line = f"Open in the browser: {urls[0]}\n" if urls else ( # We pick the first url from the urls and attach that as part of the log

        "No url in the log yet - try http://127.0.0.1:3000" # if no urls are there we return this
        "and check list_jobs if it is blank.\n"
    )

    return (
        f"{url_line}\n"
        f"Started background job (pid={proc.pid}).\n"
        f"Log: {log_path}\n"
        f"cwd={cwd}\n"
        f"Use list_jobs/stop_job to manage it.\n"
        f"------ output so far -------\n {_clip(tail) or 'No output yet.'}"
    )


@tool
def stop_job(pid: int) -> str:
    """
    Stop a background job previously started by run_command.
    Args:
        pid: The process id of the job to stop.
    """
    return stop_pid(pid)


@tool
def run_command(command: str, background: bool = False, timeout_seconds: int = 0) -> str:
    """
    Run a bash command in the working directory (host machine, not a sandbox).

    Foreground commands wait for completion. Set background=True for servers like (flask, uvicorn, npm start)
    so they keep running. Server-like commands are auto backgrounded even if you forget the flag.

    Args:
        command: bash command to run, e.g. 'python app.py' or 'ls -la'.
        background: If true, start the process and return pid immediately..
        timeout_seconds: Maximum time to wait for the command to complete. This is for foreground timeout. 0 uses default (30s).

    """

    blocked = deny_command(command)
    if blocked:
        return blocked

    timeout = timeout_seconds if timeout_seconds > 0 else DEFAULT_TIMEOUT

    background = bool(background) or looks_like_server(command)

    command = rewrite_command(command)

    if background:
        return _run_background(command)
    else:
        return _run_forground(command, timeout)


@tool
def list_jobs() -> str:
    """
    List background processes started by run_command (servers, long jobs).
    """

    jobs = all_jobs()
    if not jobs:
        return "No background jobs running."

    lines = []
    for job in jobs:
        state = "running" if is_alive(job.pid) else "exited"
        lines.append(
            f"pid={job.pid} state={state} started={job.started_at} cmd={job.command}"
        )
        tail = read_log_tail(job.log_path, max_chars=800) # we take the logs from the particular job

        if tail:
            lines.append(tail.rstrip())
            lines.append("--------------------------------") # Seperatting one job's log lines from others

        return "\n".join(lines)
