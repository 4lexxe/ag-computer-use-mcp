import json
import threading
from unittest.mock import Mock

import pytest

from windows_computer_use import server, session_state
from windows_computer_use.idle_indicator import IdleIndicator


def test_idle_closes_once_but_status_checks_do_not_keep_it_alive():
    now = [100.0]
    close = Mock()
    guard = IdleIndicator(close, threading.RLock(), clock=lambda: now[0])
    guard.touch()
    now[0] = 107.9
    assert not guard.check()
    now[0] = 108.0
    assert guard.check()
    assert not guard.check()
    close.assert_called_once()


def test_long_or_failed_tool_starts_idle_countdown_only_after_returning():
    now = [100.0]
    close = Mock()
    guard = IdleIndicator(close, threading.RLock(), clock=lambda: now[0])
    guard.touch()

    @guard.track
    def failing_tool():
        now[0] += 60
        assert not guard.check()
        raise ValueError("Application unavailable")

    with pytest.raises(ValueError):
        failing_tool()
    assert guard.active_calls == 0
    assert not guard.check()
    now[0] += 8
    assert guard.check()
    close.assert_called_once()


def test_idle_hides_then_next_action_reopens_without_overriding_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(session_state, "STATUS_FILE", tmp_path / "state.json")
    monkeypatch.setattr(server, "OVERLAY_PROCESS", None)
    guard = server.INDICATOR_GUARD
    now = [100.0]
    monkeypatch.setattr(guard, "clock", lambda: now[0])
    monkeypatch.setattr(guard, "last_activity", None)
    monkeypatch.setattr(guard, "active_calls", 0)
    process = Mock(pid=123)
    process.poll.return_value = None
    spawn = Mock(return_value=process)
    monkeypatch.setattr(server.subprocess, "Popen", spawn)

    def type_slowly(text, interval):
        now[0] += 20
        assert not guard.check(), "Never hide while input is still being sent"

    monkeypatch.setattr(server.pyautogui, "write", type_slowly)
    press = Mock()
    monkeypatch.setattr(server.pyautogui, "press", press)
    assert json.loads(server.keyboard_type("hello"))["status"] == "ok"
    now[0] += 7
    server.get_control_status()
    assert not guard.check()
    now[0] += 1
    assert guard.check()
    assert session_state.read_status()["status"] == "close"
    assert server.OVERLAY_PROCESS is None
    assert json.loads(server.keyboard_press_key("enter"))["status"] == "ok"
    assert spawn.call_count == 2
    press.assert_called_once_with("enter")

    session_state.write_status("cancelled")
    now[0] += 8
    assert guard.check()
    assert session_state.read_status()["status"] == "cancelled"
    assert json.loads(server.keyboard_press_key("enter"))["code"] == "SCREEN_SESSION_STOPPED"
    assert spawn.call_count == 2
