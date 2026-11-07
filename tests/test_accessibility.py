import subprocess
import time
from types import SimpleNamespace
from unittest.mock import Mock

from windows_computer_use import accessibility as a11y
from windows_computer_use import server, session_state


def element(element_id="1:2", name="Guardar", **extra):
    return {
        "element_id": element_id,
        "name": name,
        "control_type": "Button",
        "automation_id": "save",
        "enabled": True,
        "visible": True,
        "protected": False,
        "bounds": [0, 0, 100, 30],
        **extra,
    }


def test_snapshot_ids_are_real_and_expire(monkeypatch):
    monkeypatch.setattr(a11y, "_snapshots", {})
    worker = Mock(return_value={"status": "ok", "process_id": 123, "elements": [element()]})
    monkeypatch.setattr(a11y, "worker_request", worker)
    snapshot = a11y.inspect(456)
    token = snapshot["snapshot_id"]
    assert a11y.invoke(999, token, "1:2")["code"] == "STALE_SNAPSHOT"
    assert a11y.invoke(456, token, "guessed")["code"] == "UNKNOWN_ELEMENT"
    a11y._snapshots[token]["created"] = time.monotonic() - 31
    assert a11y.invoke(456, token, "1:2")["code"] == "STALE_SNAPSHOT"
    worker.assert_called_once()


def test_invoke_consumes_snapshot_so_it_cannot_be_replayed(monkeypatch):
    monkeypatch.setattr(a11y, "_snapshots", {})
    worker = Mock(
        side_effect=[
            {"status": "ok", "process_id": 123, "elements": [element()]},
            {"status": "ok", "refresh_required": True},
        ]
    )
    monkeypatch.setattr(a11y, "worker_request", worker)
    snapshot = a11y.inspect(456)
    assert a11y.invoke(456, snapshot["snapshot_id"], "1:2")["status"] == "ok"
    assert a11y.invoke(456, snapshot["snapshot_id"], "1:2")["code"] == "STALE_SNAPSHOT"
    assert worker.call_count == 2


def test_provider_timeout_is_returned_as_recoverable_error(monkeypatch):
    monkeypatch.setattr(
        a11y.subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("worker", 8))
    )
    assert a11y.worker_request({"action": "inspect"})["code"] == "ACCESSIBILITY_TIMEOUT"


class FakeControl:
    def __init__(self, name="Guardar", protected=False):
        self.element_info = SimpleNamespace(
            runtime_id=[1, 2],
            name=name,
            automation_id="save",
            control_type="Button",
            process_id=123,
            element=SimpleNamespace(CurrentIsPassword=protected),
        )
        self.invoke = Mock()

    def rectangle(self):
        return SimpleNamespace(left=0, top=0, right=100, bottom=30)

    def is_enabled(self):
        return True

    def is_visible(self):
        return True

    def children(self):
        return []

    def window_text(self):
        return "Proyecto A"


def test_protected_fields_do_not_leak_their_contents():
    description = a11y.describe(FakeControl(name="super-secret", protected=True))
    assert description["name"] == "[campo protegido]"
    assert description["protected"]


def test_changed_control_is_never_invoked():
    control = FakeControl(name="Eliminar")
    desktop = Mock()
    desktop.window.return_value.wrapper_object.return_value = control
    result = a11y.run_worker(
        {
            "action": "invoke",
            "hwnd": 456,
            "process_id": 123,
            "depth": 5,
            "expected": element(name="Guardar"),
        },
        desktop=desktop,
    )
    assert result["code"] == "ELEMENT_CHANGED"
    control.invoke.assert_not_called()


def test_cancel_blocks_both_new_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(session_state, "STATUS_FILE", tmp_path / "state.json")
    session_state.write_status("cancelled")
    worker = Mock(side_effect=AssertionError("A cancelled tool must not launch a worker"))
    monkeypatch.setattr(a11y, "worker_request", worker)
    assert "SCREEN_SESSION_STOPPED" in server.inspect_window(456)
    assert "SCREEN_SESSION_STOPPED" in server.invoke_control(456, "token", "1:2")
    worker.assert_not_called()
