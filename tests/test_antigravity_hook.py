import json
import os
import subprocess
import sys
from pathlib import Path

from windows_computer_use import antigravity_hook, session_state


def test_install_preserves_other_hooks_and_is_idempotent(tmp_path):
    path = tmp_path / "hooks.json"
    existing = {"existing": {"Stop": [{"command": "echo unchanged"}]}}
    path.write_text(json.dumps(existing), encoding="utf-8")
    antigravity_hook.install(path, python=sys.executable)
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["existing"] == existing["existing"]
    handler = result[antigravity_hook.HOOK_NAME]["Stop"][0]
    assert "windows_computer_use.antigravity_hook" in handler["command"]
    assert "hooks" not in handler  # Stop handlers have no tool-matcher wrapper.
    backups = list(tmp_path.glob("hooks.before-*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8")) == existing
    antigravity_hook.install(path, python=sys.executable)
    assert list(tmp_path.glob("hooks.before-*.json")) == backups


def test_stop_closes_visual_session_and_preserves_cancellation(tmp_path, monkeypatch):
    monkeypatch.setattr(session_state, "STATUS_FILE", tmp_path / "state.json")
    monkeypatch.setattr(session_state, "state_directory", lambda: tmp_path)
    payload = {"terminationReason": "model_stop", "fullyIdle": True, "lastUserInput": "private"}
    session_state.write_status("active")
    antigravity_hook.on_stop(payload)
    assert session_state.read_status()["status"] == "close"
    assert "private" not in (tmp_path / "last_antigravity_stop.json").read_text()
    session_state.write_status("cancelled")
    antigravity_hook.on_stop(payload)
    assert session_state.read_status()["status"] == "cancelled"


def test_background_tasks_and_invalid_payload_do_not_close(tmp_path, monkeypatch):
    monkeypatch.setattr(session_state, "STATUS_FILE", tmp_path / "state.json")
    monkeypatch.setattr(session_state, "state_directory", lambda: tmp_path)
    session_state.write_status("active")
    antigravity_hook.on_stop({"terminationReason": "model_stop", "fullyIdle": False})
    antigravity_hook.on_stop({})
    assert session_state.read_status()["status"] == "active"


def test_hook_process_uses_explicit_state_dir_and_allows_stop(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "windows_computer_use.antigravity_hook",
            "--state-dir",
            str(tmp_path),
        ],
        input=json.dumps({"terminationReason": "error", "fullyIdle": True}),
        text=True,
        capture_output=True,
        timeout=5,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        },
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"decision": "allow"}
    assert json.loads((tmp_path / "overlay_status.json").read_text())["status"] == "close"
