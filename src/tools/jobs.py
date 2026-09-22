import contextlib
import os
import signal

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import subprocess  # Using the subprocess command we will be able to spin up a new sub process and run a valid shell command, we can also control where the output of
# the command goes


# There can be process which can be running in the background
@dataclass
class BackgroundJob:
    pid: int # Each process that is spin up has unique id which is of int
    command: str # This is the bash command that got executed which created this process
    started_at: str # The time in which this process has started
    log_path: Path | str # This is the file path the logs for this process gets stored
    proc: Any = field(default=None, repr=False) # this 'proc' field holds the python wrapper of the process and the default value is None , repr = False makes this
                                                # 'proc' field not to appear when we are doing any sort of printing of this BackgroundJob object.
                                                # This 'proc' property will have value when this background job is created by the agent
                                                # basically this process is created by the subprocess from the agent. And then we have the python wrapper
                                                # of that process will be in this 'proc' field


_JOBS: dict[int, BackgroundJob] = {} # This is the place we are going to keep track of all the background jobs(within each job we have the actual
# process also maintained) that are being created


def register(job: BackgroundJob) -> None:
    _JOBS[job.pid] = job


def get(pid: int) -> BackgroundJob | None:
    return _JOBS.get(pid)


def all_jobs() -> list[BackgroundJob]:
    return list(_JOBS.values())


def remove(pid: int) -> BackgroundJob | None:
    return _JOBS.pop(pid, None)


def is_alive(pid: int) -> bool:
    job = get(pid)
    if job is not None and job.proc is not None: # We are checking if there is any background job with that process id and there is any actual python wrapper
                                                # for that process available
        return job.proc.poll() is None # This poll checks if the job is still alive, if the .poll() is None then the process is alive

    # if we are not able to find a background job instance with the provided process id,
    try:
        os.kill(pid, 0) # this os.kill(pid,0) just checks if the process exists and currently running(liveness check)
        return True
    except OSError:
        return False # if there is any error while checking the process's liveness


def stop_pid(pid: int) -> str:
    job = get(pid)
    if job is None:
        return f"Error: {pid} is not a job started by this agent." # If the job is not maintained or created by the agent we are just returning
    if not is_alive(pid):
        if job.proc is not None: # We are verifying the python wrapper for the process is existing
            with contextlib.suppress(ChildProcessError): # This contextlib.suppress is to suppress this specific error
                job.proc.wait(timeout=0.1) # So here we wait until all the associations of the child process is killed and collected
                                            # since this sub-process is already killed we just wait and collect the exit status alone
        remove(pid) # And then we just remove this job from being tracked
        return f"Job {pid} was already stopped."
    try:
        # The process is alive and we wanted to kill the process
        # killpg ,will kill the entire process group(which has multiple processes) that are associated with the particular process id group
        # We are doing this because there can be a chance that when the agent is trying to start a server process it might spin multiple other process as well
        # so in that case when there are tree of process's that are there and if we wanted to kill all of them at once we use this.

        os.killpg(pid, signal.SIGTERM) # we are providing the sigterm which will terminate the proces(along with child process), this is for gracefull
                                        # way wait for shutdown hooks
    except ProcessLookupError:
        remove(pid) # if the process is not present when we are trying to kill so in that case we just remove it
        return f"Job {pid} was already gone."
    except PermissionError as err:
        return f"Error stopping {pid}: {err}"

    # if during the SIGTERM due to some reason the process of shutdown didn't happen successfully
    if job.proc is not None: # Then we are again trying to do force kill
        try:
            job.proc.wait(timeout=1.5) # We first wait until the process gets terminated because of the above sigterm
        except subprocess.TimeoutExpired: # if the timeout happens
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGKILL) # Then we try to kill it forefully the main process and all the tree of processes
            with contextlib.suppress(subprocess.TimeoutExpired):
                job.proc.wait(timeout=1) # We are again waiting until the forcekill works
    remove(pid)
    return f"Sent SIGTERM to process group {pid} ({job.command!r})."


def read_log_tail(log_path: Path, *, max_chars: int = 4000) -> str:
    if not log_path.is_file(): # We are checking if the path given is proper fiel
        return ""
    text = log_path.read_text(encoding="utf-8", errors="replace") # This 'errors' replace loads the file without any errors
    if len(text) > max_chars:
        return text[-max_chars:] # We are returning the last max_chars from the file
    return text


def now_iso() -> str:
    return datetime.now(UTC).isoformat()