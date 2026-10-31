import os
import signal
import subprocess
from math import isfinite
from platform import system
from time import (
    monotonic,
    sleep,
)
from typing import (
    Callable,
    TYPE_CHECKING,
)

try:
    from psutil import (
        NoSuchProcess,
        Process,
        STATUS_ZOMBIE,
    )
except ImportError:
    """Don't make psutil a strict requirement, but use if available."""
    if not TYPE_CHECKING:
        Process = None


def kill_pid(pid: int, use_psutil: bool = True, grace_period: float = 5):
    """Terminate a job tree, allowing POSIX cleanup before killing survivors.

    ``grace_period`` bounds the SIGTERM wait in seconds. On Windows psutil
    terminate, like taskkill /F, stops processes without a grace period.
    On POSIX, if ``pid`` leads a process group, survivors in that group are
    killed too, including processes reparented away from ``pid`` during cleanup.
    """
    if not isfinite(grace_period) or grace_period < 0:
        raise ValueError("grace_period must be finite and nonnegative")
    if use_psutil and Process is not None:
        _psutil_kill_pid(pid, grace_period)
    else:
        _stock_kill_pid(pid, grace_period)


def _psutil_kill_pid(pid: int, grace_period: float = 5):
    try:
        parent = Process(pid)
        # psutil lists each process before its descendants.
        processes = [parent, *parent.children(recursive=True)]
    except NoSuchProcess:
        return
    sweep_group = _is_group_leader(pid)

    # Signal waiting shells first: terminating a child can start its shell's
    # EXIT trap, which a later TERM to that shell would interrupt.
    for process in processes:
        try:
            process.terminate()
        except NoSuchProcess:
            pass

    def done() -> bool:
        nonlocal sweep_group
        # Once the group is empty its id may be reused, so stop tracking it.
        sweep_group = sweep_group and _group_exists(pid)
        return not any(_is_running(p) for p in processes)

    # Not psutil.wait_procs: it reaps children of this process, racing the
    # manager's Popen.wait on the job's root process for its exit status.
    _wait_until(done, grace_period)
    alive = [process for process in processes if _is_running(process)]
    # EXIT handlers may start cleanup commands during the grace period.
    survivors = set(alive)
    for process in alive:
        try:
            survivors.update(process.children(recursive=True))
        except NoSuchProcess:
            pass
    for process in survivors:
        try:
            process.kill()
        except NoSuchProcess:
            pass
    if sweep_group:
        # Cleanup commands whose parent exited left the tree but not the group.
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass


def _is_running(process: "Process") -> bool:
    try:
        return process.is_running() and process.status() != STATUS_ZOMBIE
    except NoSuchProcess:
        return False


def _is_group_leader(pid: int) -> bool:
    if os.name != "posix":
        return False
    try:
        return os.getpgid(pid) == pid
    except OSError:
        return False


def _wait_until(done: Callable[[], bool], timeout: float) -> None:
    deadline = monotonic() + timeout
    while not done():
        remaining = deadline - monotonic()
        if remaining <= 0:
            return
        sleep(min(0.05, remaining))


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except OSError:
        return False


def _stock_kill_pid(pid: int, grace_period: float = 5):
    is_windows = system() == "Windows"

    if is_windows:
        __kill_windows(pid)
    else:
        __kill_posix(pid, grace_period)


def __kill_windows(pid):
    try:
        subprocess.check_call(["taskkill", "/F", "/T", "/PID", str(pid)])
    except subprocess.CalledProcessError:
        pass


def __kill_posix(pid: int, grace_period: float = 5):
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        return
    # Wait on the whole group: the leader may exit while a shell it started
    # is still running its EXIT trap.
    _wait_until(lambda: not _group_exists(pid), grace_period)
    # Once the group is empty its id may be reused, so only kill a live group.
    if _group_exists(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass
