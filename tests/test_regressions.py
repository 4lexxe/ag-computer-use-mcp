import asyncio
import io
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from windows_computer_use import screen_capture, server, session_state


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    monkeypatch.setattr(session_state, "STATUS_FILE", tmp_path / "status.txt")
    return session_state.STATUS_FILE


def test_cancel_survives_every_action_and_hide(state_file, monkeypatch):
    session_state.write_status("cancelled")
    spawn = Mock(side_effect=AssertionError("Cancelled session must not spawn an overlay"))
    monkeypatch.setattr(server.subprocess, "Popen", spawn)
    actions = [
        lambda: server.mouse_move(1, 1),
        server.mouse_click,
        lambda: server.mouse_drag(1, 1, 2, 2),
        lambda: server.mouse_scroll(1),
        lambda: server.keyboard_type("test"),
        lambda: server.keyboard_press_key("enter"),
        lambda: server.keyboard_hotkey(["ctrl", "c"]),
        server.take_screenshot,
        lambda: server.focus_window_by_title("project"),
    ]
    for action in actions:
        response = json.loads(action())
        assert response["status"] == "aborted"
        assert response["code"] == "SCREEN_SESSION_STOPPED"
        assert response["recovery_tool"] == "resume_screen_control"
    assert json.loads(server.read_screen()[0])["status"] == "aborted"
    server.hide_screen_overlay()
    assert server.check_user_cancelled()
    spawn.assert_not_called()


def test_explicit_resume_keeps_project_and_has_no_startup_sleep(state_file, monkeypatch):
    session_state.write_status("cancelled")
    process = Mock(pid=123)
    process.poll.return_value = None
    monkeypatch.setattr(server, "OVERLAY_PROCESS", None)
    spawn = Mock(return_value=process)
    monkeypatch.setattr(server.subprocess, "Popen", spawn)
    server.show_screen_overlay("Proyecto Águila")
    server.ensure_overlay_visible()
    assert session_state.read_status() == {
        "status": "active",
        "project_name": "Proyecto Águila",
        "activity": "interacting",
    }
    spawn.assert_called_once()


def test_status_does_not_resume_and_explicit_recovery_unblocks_action(state_file, monkeypatch):
    session_state.write_status("cancelled")
    monkeypatch.setattr(server, "OVERLAY_PROCESS", None)
    process = Mock(pid=123)
    process.poll.return_value = None
    spawn = Mock(return_value=process)
    monkeypatch.setattr(server.subprocess, "Popen", spawn)
    keypress = Mock()
    monkeypatch.setattr(server.pyautogui, "press", keypress)
    state = json.loads(server.get_control_status())
    assert state["status"] == "cancelled"
    assert state["requires_user_request_to_resume"]
    spawn.assert_not_called()
    assert json.loads(server.keyboard_press_key("enter"))["code"] == "SCREEN_SESSION_STOPPED"
    keypress.assert_not_called()
    result = asyncio.run(
        server.mcp.call_tool("resume_screen_control", {"project_name": "Proyecto actual"})
    )
    assert not result.is_error
    assert session_state.read_status()["status"] == "active"
    assert json.loads(server.keyboard_press_key("enter"))["status"] == "ok"
    keypress.assert_called_once_with("enter")
    spawn.assert_called_once()


def test_state_compatibility_and_corruption(state_file):
    state_file.write_text("cancelled", encoding="utf-8")
    assert server.check_user_cancelled()
    state_file.write_text("{broken", encoding="utf-8")
    assert server.check_user_cancelled()


def test_stop_interrupts_long_typing_between_small_chunks(state_file, monkeypatch):
    session_state.write_status("active")
    monkeypatch.setattr(server, "ensure_overlay_visible", lambda **kwargs: None)

    def stop_after_first_chunk(text, interval):
        session_state.write_status("cancelled")

    writer = Mock(side_effect=stop_after_first_chunk)
    monkeypatch.setattr(server.pyautogui, "write", writer)
    response = json.loads(server.keyboard_type("x" * 200))
    assert response["code"] == "SCREEN_SESSION_STOPPED"
    assert response["typed_length"] == 8
    writer.assert_called_once_with("x" * 8, interval=0.02)


class FakeCapture:
    monitors = [
        dict(left=-1200, top=0, width=3120, height=1080),
        dict(left=0, top=0, width=1920, height=1080),
    ]

    def grab(self, bounds):
        image = Image.new("RGB", (bounds["width"], bounds["height"]), "white")
        return type("Shot", (), {"size": image.size, "bgra": image.tobytes("raw", "BGRX")})()

    def close(self):
        pass


@pytest.fixture
def fake_capture(monkeypatch):
    monkeypatch.setattr(screen_capture, "_local", type("Cache", (), {})())
    monkeypatch.setattr(screen_capture.mss, "MSS", FakeCapture)


def test_region_scaling_and_negative_monitor_origin(fake_capture):
    info, payload = screen_capture.capture_screen(600, region=[-1100, 40, 900, 600])
    assert (info["origin_x"], info["origin_y"]) == (-1100, 40)
    assert info["scale_x"] == info["scale_y"] == 1.5
    assert Image.open(io.BytesIO(payload)).size == (600, 400)
    info, _ = screen_capture.capture_screen(None, monitor=0)
    assert info["origin_x"] == -1200
    assert info["scale_x"] == 1


@pytest.mark.parametrize(
    "arguments",
    [
        dict(max_dimension=-1),
        dict(quality=0),
        dict(monitor=9),
        dict(region=[0, 0, 0, 100]),
        dict(region=[1]),
    ],
)
def test_invalid_capture_arguments(fake_capture, arguments):
    with pytest.raises(ValueError):
        screen_capture.capture_screen(**arguments)


def test_native_mcp_image_content(state_file, fake_capture, monkeypatch):
    session_state.write_status("active")
    monkeypatch.setattr(server, "ensure_overlay_visible", lambda **kwargs: None)
    result = asyncio.run(server.mcp.call_tool("read_screen", {"max_dimension": 800}))
    assert not result.is_error
    assert [block.type for block in result.content] == ["text", "image"]
    assert result.content[1].mime_type == "image/jpeg"
    assert json.loads(result.content[0].text)["preview_width"] == 800


def test_similar_project_windows_require_explicit_selection(state_file, monkeypatch):
    session_state.write_status("active")
    monkeypatch.setattr(server, "ensure_overlay_visible", lambda **kwargs: None)
    titles = {101: "Proyecto A - Editor", 102: "Proyecto B - Editor"}
    user32 = SimpleNamespace(
        IsWindowVisible=lambda hwnd: True,
        GetWindowTextLengthW=lambda hwnd: len(titles[hwnd]),
        GetWindowTextW=lambda hwnd, buffer, length: setattr(buffer, "value", titles[hwnd]),
        EnumWindows=lambda callback, extra: [callback(hwnd, extra) for hwnd in titles],
    )
    monkeypatch.setattr(server.ctypes.windll, "user32", user32)
    result = json.loads(server.focus_window_by_title("Editor"))
    assert result["status"] == "ambiguous"
    assert [window["hwnd"] for window in result["windows"]] == [101, 102]
    assert json.loads(server.focus_window_by_title())["status"] == "error"


def test_exact_window_id_preserves_maximized_window(state_file, monkeypatch):
    session_state.write_status("active")
    monkeypatch.setattr(server, "ensure_overlay_visible", lambda **kwargs: None)
    titles = {101: "Proyecto A - Editor", 102: "Proyecto B - Editor"}
    user32 = SimpleNamespace(
        IsWindowVisible=lambda hwnd: True,
        GetWindowTextLengthW=lambda hwnd: len(titles[hwnd]),
        GetWindowTextW=lambda hwnd, buffer, length: setattr(buffer, "value", titles[hwnd]),
        EnumWindows=lambda callback, extra: [callback(hwnd, extra) for hwnd in titles],
        GetForegroundWindow=lambda: 102,
        GetWindowThreadProcessId=lambda hwnd, pointer: 20,
        AttachThreadInput=Mock(return_value=True),
        IsIconic=lambda hwnd: False,
        ShowWindow=Mock(),
        BringWindowToTop=Mock(),
        SetForegroundWindow=Mock(),
    )
    monkeypatch.setattr(server.ctypes.windll, "user32", user32)
    result = json.loads(server.focus_window_by_title(hwnd=102))
    assert result["status"] == "focused"
    assert result["matched_title"] == titles[102]
    user32.SetForegroundWindow.assert_called_once_with(102)
    user32.ShowWindow.assert_not_called()
    calls = user32.AttachThreadInput.call_args_list
    assert sum(call.args[2] is True for call in calls) == sum(
        call.args[2] is False for call in calls
    )
