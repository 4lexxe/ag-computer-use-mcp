"""Distribution boundaries and user-state isolation."""

import importlib.util
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from windows_computer_use import __version__, session_state

ROOT = Path(__file__).resolve().parents[1]


def load_release_builder():
    spec = importlib.util.spec_from_file_location(
        "build_release", ROOT / "scripts/build_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_versions_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__


def test_release_allowlist_excludes_private_files(tmp_path):
    builder = load_release_builder()
    for name in (
        "src/windows_computer_use/server.py",
        "src/secret.egg-info/data.py",
        "src/__pycache__/secret.py",
        ".local/reference-captures/private.jpg",
        "tests/test_example.py",
        "docs/usage.md",
        "docs/media/antigravity-in-action.gif",
        "docs/media/antigravity-in-action.mp4",
        "docs/media/raw.mp4",
        "examples/mcp_config.json",
        "scripts/secret.env",
        "src/windows_computer_use/overlay_status.json",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("example", encoding="utf-8")
    files = {path.relative_to(tmp_path).as_posix() for path in builder.source_files(tmp_path)}
    assert "src/windows_computer_use/server.py" in files
    assert "tests/test_example.py" in files
    assert "docs/media/antigravity-in-action.gif" in files
    assert "docs/media/antigravity-in-action.mp4" in files
    assert "docs/media/raw.mp4" not in files
    assert not any(
        ".local" in name or "__pycache__" in name or ".egg-info" in name for name in files
    )
    assert "scripts/secret.env" not in files
    # A matching extension must not accidentally permit a runtime state file.
    assert not any("overlay_status" in name for name in files)


def test_state_override_and_nested_directory_creation(tmp_path, monkeypatch):
    directory = tmp_path / "user" / "runtime"
    monkeypatch.setenv("WINDOWS_COMPUTER_USE_STATE_DIR", str(directory))
    assert session_state.state_directory() == directory.resolve()
    monkeypatch.setattr(session_state, "STATUS_FILE", directory / "overlay_status.json")
    session_state.write_status("cancelled")
    assert session_state.read_status()["status"] == "cancelled"


def test_import_does_not_create_or_modify_state(tmp_path):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    directory = tmp_path / "state"
    environment["WINDOWS_COMPUTER_USE_STATE_DIR"] = str(directory)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import windows_computer_use.server; import windows_computer_use.overlay",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not directory.exists()
