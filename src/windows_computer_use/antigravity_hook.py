"""Antigravity Stop hook: close this indicator when an agent run finishes."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOK_NAME = "ag-computer-use-cleanup"


def install(config_path, python=sys.executable, state_dir=None):
    config_path = Path(config_path).expanduser().resolve()
    existing = config_path.read_text(encoding="utf-8-sig") if config_path.exists() else None
    config = json.loads(existing) if existing else {}
    if not isinstance(config, dict):
        raise ValueError("hooks.json must contain an object")
    command = [str(Path(python).resolve()), "-m", "windows_computer_use.antigravity_hook"]
    if state_dir:
        command += ["--state-dir", str(Path(state_dir).expanduser().resolve())]
    config[HOOK_NAME] = {
        "Stop": [{"type": "command", "command": subprocess.list2cmdline(command), "timeout": 5}]
    }
    result = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    if existing == result:
        return config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if existing is not None:
        shutil.copy2(
            config_path, config_path.with_name(f"hooks.before-ag-cleanup-{time.time_ns()}.json")
        )
    _atomic_json(config_path, config)
    return config_path


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ag-hook-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def on_stop(payload):
    from .session_state import STATUS_FILE, close_if_not_cancelled, read_status, state_directory

    if not isinstance(payload, dict) or not isinstance(payload.get("terminationReason"), str):
        return
    before = read_status()["status"]
    finished = payload.get("fullyIdle", True) is not False
    if finished:
        close_if_not_cancelled()
    # Local operational metadata only: never store prompts, transcripts or results.
    _atomic_json(
        state_directory() / "last_antigravity_stop.json",
        {
            "received_at": time.time(),
            "conversation_id": payload.get("conversationId"),
            "termination_reason": payload["terminationReason"],
            "fully_idle": finished,
            "indicator_close_requested": finished,
            "state_file": str(STATUS_FILE),
            "status_before": before,
            "status_after": read_status()["status"],
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--config", type=Path, default=Path.home() / ".gemini/config/hooks.json")
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    if args.state_dir:
        os.environ["WINDOWS_COMPUTER_USE_STATE_DIR"] = str(args.state_dir.expanduser().resolve())
    if args.install:
        print(install(args.config, state_dir=args.state_dir))
        return
    try:
        payload = json.loads(sys.stdin.read(1_048_576))
        on_stop(payload)
    except (OSError, ValueError, TypeError) as error:
        print(f"Screen indicator cleanup: {type(error).__name__}", file=sys.stderr)
    # Never extend the run, inject a message or alter permissions.
    print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
