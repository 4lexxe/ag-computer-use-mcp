"""Atomic IPC state stored in a user-writable directory outside the package."""

import json
import msvcrt
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path


def state_directory():
    override = os.environ.get("WINDOWS_COMPUTER_USE_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "WindowsComputerUseMCP"


STATUS_FILE = state_directory() / "overlay_status.json"
_thread_lock = threading.RLock()


@contextmanager
def state_lock():
    """Serialize read-modify-write across the server and indicator processes."""
    with _thread_lock:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with (STATUS_FILE.parent / "overlay.lock").open("a+b") as handle:
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            deadline = time.monotonic() + 3
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.01)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def read_status():
    try:
        raw = STATUS_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return {"status": "close"}
    if raw in ("active", "close", "cancelled"):
        return {"status": raw}
    try:
        state = json.loads(raw)
        if isinstance(state, dict) and state.get("status") in ("active", "close", "cancelled"):
            return state
    except (ValueError, TypeError):
        pass
    return {"status": "cancelled"}


def write_status(status, project_name=None, activity=None):
    if status not in ("active", "close", "cancelled"):
        raise ValueError("Unknown screen-control status")
    state = {"status": status}
    if project_name is not None:
        state["project_name"] = project_name
    if activity is not None:
        state["activity"] = activity
    with state_lock():
        _write_state(state)


def set_activity(activity):
    with state_lock():
        state = read_status()
        if state["status"] != "active" or state.get("activity") == activity:
            return
        state["activity"] = activity
        _write_state(state)


def close_if_not_cancelled():
    """Atomically close the visual session without racing the user's Stop action."""
    with state_lock():
        if read_status()["status"] != "cancelled":
            _write_state({"status": "close"})


def _write_state(state):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".overlay-", dir=STATUS_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False)
        for attempt in range(5):
            try:
                os.replace(temporary, STATUS_FILE)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
