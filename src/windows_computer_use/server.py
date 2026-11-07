import atexit
import base64
import ctypes
import json
import os
import subprocess
import sys
import threading
from ctypes import wintypes
from typing import List, Optional

import pyautogui
from mcp.server.mcpserver import Image as MCPImage
from mcp.server.mcpserver import MCPServer

from . import accessibility
from .antigravity_lifecycle import AntigravityRunMonitor
from .idle_indicator import IdleIndicator
from .screen_capture import capture_screen
from .session_state import close_if_not_cancelled, read_status, set_activity, write_status

# Overlay process management
OVERLAY_PROCESS: Optional[subprocess.Popen] = None
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_LOCK = threading.RLock()
INDICATOR_IDLE_SECONDS = 8.0
INDICATOR_GUARD = IdleIndicator(
    lambda: hide_screen_overlay(), SESSION_LOCK, timeout=INDICATOR_IDLE_SECONDS
)

# Explicit pointer-sized signatures prevent HWND truncation on 64-bit Windows.
_user32 = ctypes.windll.user32
for _name, _args, _result in (
    ("IsWindowVisible", [wintypes.HWND], wintypes.BOOL),
    ("GetWindowTextLengthW", [wintypes.HWND], ctypes.c_int),
    ("GetWindowTextW", [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
    ("GetWindowRect", [wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
    ("GetForegroundWindow", [], wintypes.HWND),
    ("GetWindowThreadProcessId", [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
    ("ShowWindow", [wintypes.HWND, ctypes.c_int], wintypes.BOOL),
    ("BringWindowToTop", [wintypes.HWND], wintypes.BOOL),
    ("SetForegroundWindow", [wintypes.HWND], wintypes.BOOL),
    ("IsIconic", [wintypes.HWND], wintypes.BOOL),
):
    getattr(_user32, _name).argtypes = _args
    getattr(_user32, _name).restype = _result


def attach_to_default_desktop():
    # Stay on the caller's interactive desktop; do not leak an HDESK per action.
    return


def ensure_overlay_visible(restart=False, project_name=None, activity="interacting"):
    """Ensure the glowing border overlay is running and visible."""
    global OVERLAY_PROCESS
    with SESSION_LOCK:
        if check_user_cancelled() and not restart:
            return
        if restart or read_status()["status"] != "active":
            write_status("active", project_name, activity=activity)
        else:
            set_activity(activity)
        INDICATOR_GUARD.touch()
        if OVERLAY_PROCESS is None or OVERLAY_PROCESS.poll() is not None:
            run = AntigravityRunMonitor()
            environment = {**os.environ, "WINDOWS_COMPUTER_USE_PARENT_PID": str(os.getpid())}
            if run.owner:
                environment["WINDOWS_COMPUTER_USE_RUN_DB"] = run.owner[0]
                environment["WINDOWS_COMPUTER_USE_RUN_ID"] = run.owner[1]
            OVERLAY_PROCESS = subprocess.Popen(
                [sys.executable, "-m", "windows_computer_use.overlay"],
                cwd=os.path.dirname(SCRIPT_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
            )


def check_user_cancelled() -> bool:
    return read_status()["status"] == "cancelled"


def cancellation_response() -> str:
    return json.dumps(
        {
            "status": "aborted",
            "code": "SCREEN_SESSION_STOPPED",
            "source": "windows-computer-use",
            "error": "The screen-control session is stopped. This is stored MCP session state, not a host permission-dialog rejection.",
            "recovery_tool": "resume_screen_control",
            "next_step": "If the user has asked to continue (for example 'si' or 'listo, usa el MCP'), call resume_screen_control, then retry the requested MCP action. Otherwise wait for the user. Do not bypass this stop with terminal/system commands.",
        },
        ensure_ascii=False,
    )


# Safety settings for PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

mcp = MCPServer(
    "WindowsComputerUse",
    instructions=(
        "Control the Windows desktop. Prefer read_screen for native image content and "
        "list_open_windows to locate the existing project window. Prefer inspect_window for "
        "a UI Automation control snapshot and invoke_control for controls exposing Invoke. "
        "Use fresh snapshot_id and element_id values only; never guess them. "
        "Focus the target window by hwnd before invoking a control. Use its hwnd to focus "
        "unambiguously. Screenshot previews may be scaled: use the returned scale_x, "
        "scale_y and origin to convert preview pixels to desktop coordinates. After "
        "cancellation, resume only when the user asks, using resume_screen_control "
        "(or show_screen_overlay for older clients). A user reply such as 'si', "
        "'listo ya esta usa el mcp', or 'continua' authorizes resuming their requested task. "
        "SCREEN_SESSION_STOPPED is internal session state, NOT a rejection of a host "
        "permission dialog. Follow the recovery_tool in the response instead of retrying "
        "keyboard/mouse tools while stopped. Never bypass a stopped session using "
        "terminal/system commands. get_control_status is read-only. "
        "Always call hide_screen_overlay before your final response, including on errors. "
        "The indicator also hides after 8 seconds with no screen tools in progress; "
        "the next screen action shows it again without clearing a user's cancellation."
    ),
)


@mcp.tool()
@INDICATOR_GUARD.track
def show_screen_overlay(project_name: Optional[str] = None) -> str:
    """
    Start or explicitly resume the translucent red indicator with a Stop button.
    Optionally identify the active project in the banner.
    Indicates to the user that AI Computer Use is actively controlling the computer.
    """
    ensure_overlay_visible(restart=True, project_name=project_name, activity="ready")
    return json.dumps(
        {"status": "overlay_active", "pid": OVERLAY_PROCESS.pid if OVERLAY_PROCESS else None}
    )


@mcp.tool()
@INDICATOR_GUARD.track
def resume_screen_control(project_name: Optional[str] = None) -> str:
    """Resume a stopped MCP session AFTER the user asks to continue, then retry their action.

    Use after 'si', 'continua', or 'listo, usa el MCP'. Clears internal stopped
    state; it does not approve or change Antigravity permission dialogs.
    """
    return show_screen_overlay(project_name)


@mcp.tool()
def get_control_status() -> str:
    """Inspect internal MCP control state without starting or resuming control."""
    state = dict(read_status())
    state["overlay_running"] = OVERLAY_PROCESS is not None and OVERLAY_PROCESS.poll() is None
    state["indicator_idle_timeout_seconds"] = INDICATOR_IDLE_SECONDS
    if state["status"] == "cancelled":
        state["code"] = "SCREEN_SESSION_STOPPED"
        state["recovery_tool"] = "resume_screen_control"
        state["requires_user_request_to_resume"] = True
    return json.dumps(state, ensure_ascii=False)


@mcp.tool()
@INDICATOR_GUARD.track
def inspect_window(hwnd: int, max_elements: int = 120, depth: int = 5) -> str:
    """Read window controls using pywinauto/UI Automation. Returns IDs, labels and bounds.

    Select hwnd from list_open_windows. Values from protected inputs are excluded.
    Snapshot IDs expire after 30 seconds. Fall back to read_screen if UIA is unavailable.
    """
    ensure_overlay_visible(activity="inspecting")
    if check_user_cancelled():
        return cancellation_response()
    return json.dumps(accessibility.inspect(hwnd, max_elements, depth), ensure_ascii=False)


@mcp.tool()
@INDICATOR_GUARD.track
def invoke_control(hwnd: int, snapshot_id: str, element_id: str) -> str:
    """Invoke a control from a fresh inspect_window snapshot in the focused window.

    Never guess IDs. Reinspect after invoking. Controls without the Invoke pattern
    return an error; use read_screen and the coordinate tools for those controls.
    """
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    if _user32.GetForegroundWindow() != hwnd:
        return json.dumps(
            {
                "status": "error",
                "code": "WINDOW_NOT_FOCUSED",
                "error": "Primero enfoca la ventana del proyecto por hwnd.",
            }
        )
    result = accessibility.invoke(hwnd, snapshot_id, element_id)
    if result.get("code") == "SCREEN_SESSION_STOPPED":
        return cancellation_response()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def hide_screen_overlay() -> str:
    """
    Hide the indicator when finished. Does not clear a user's cancellation.
    """
    global OVERLAY_PROCESS
    with SESSION_LOCK:
        # Preserve cancellation until an explicit show_screen_overlay resumes it.
        close_if_not_cancelled()
        if OVERLAY_PROCESS:
            try:
                OVERLAY_PROCESS.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                OVERLAY_PROCESS.terminate()
                try:
                    OVERLAY_PROCESS.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    OVERLAY_PROCESS.kill()
                    OVERLAY_PROCESS.wait(timeout=1.0)
            OVERLAY_PROCESS = None
        INDICATOR_GUARD.disarm()
    return json.dumps({"status": "overlay_closed"})


@mcp.tool()
@INDICATOR_GUARD.track
def get_screen_resolution() -> str:
    """Get the primary screen resolution (width and height in pixels)."""
    attach_to_default_desktop()
    width, height = pyautogui.size()
    return json.dumps({"width": width, "height": height})


@mcp.tool()
@INDICATOR_GUARD.track
def take_screenshot(
    save_path: Optional[str] = None,
    max_dimension: Optional[int] = 1280,
    quality: int = 80,
    monitor: int = 1,
    region: Optional[List[int]] = None,
) -> str:
    """
    Capture the current desktop screen in real-time.
    Automatically ensures the glowing border overlay is visible while interacting.
    Returns screen dimensions and base64 encoded JPEG (scaled if larger than max_dimension for ultra-fast processing).
    Optionally saves the full-resolution screenshot to disk if save_path is provided.
    """
    # Ensure border is displayed throughout the interaction session
    ensure_overlay_visible(activity="reading")

    if check_user_cancelled():
        return cancellation_response()

    metadata, payload = capture_screen(max_dimension, quality, monitor, region, save_path)
    metadata["image_base64_jpeg"] = base64.b64encode(payload).decode("ascii")
    return json.dumps(metadata)


@mcp.tool()
@INDICATOR_GUARD.track
def read_screen(
    max_dimension: Optional[int] = 1600,
    quality: int = 80,
    monitor: int = 1,
    region: Optional[List[int]] = None,
) -> list:
    """Read the desktop as a native MCP image plus coordinate metadata.

    Prefer this over base64 text. Use a region [left, top, width, height] for small
    UI text, or max_dimension=null for full detail. monitor=0 reads all displays.
    """
    ensure_overlay_visible(activity="reading")
    if check_user_cancelled():
        return [cancellation_response()]
    metadata, payload = capture_screen(max_dimension, quality, monitor, region)
    return [json.dumps(metadata), MCPImage(data=payload, format="jpeg")]


@mcp.tool()
@INDICATOR_GUARD.track
def mouse_move(x: int, y: int, duration: float = 0.1) -> str:
    """Move mouse cursor smoothly to screen coordinates (x, y)."""
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    attach_to_default_desktop()
    pyautogui.moveTo(x, y, duration=duration)
    curr_x, curr_y = pyautogui.position()
    return json.dumps({"status": "ok", "position": [curr_x, curr_y]})


@mcp.tool()
@INDICATOR_GUARD.track
def mouse_click(
    x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1
) -> str:
    """
    Click mouse button at current or specified (x, y) coordinates.
    button: 'left', 'right', or 'middle'.
    clicks: 1 for single click, 2 for double click.
    """
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    attach_to_default_desktop()
    if x is not None and y is not None:
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
    else:
        pyautogui.click(clicks=clicks, button=button)
    curr_x, curr_y = pyautogui.position()
    return json.dumps(
        {"status": "ok", "clicked_at": [curr_x, curr_y], "button": button, "clicks": clicks}
    )


@mcp.tool()
@INDICATOR_GUARD.track
def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.3) -> str:
    """Click and drag from (start_x, start_y) to (end_x, end_y)."""
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    attach_to_default_desktop()
    pyautogui.moveTo(start_x, start_y)
    pyautogui.dragTo(end_x, end_y, duration=duration, button="left")
    return json.dumps(
        {"status": "ok", "dragged_from": [start_x, start_y], "dragged_to": [end_x, end_y]}
    )


@mcp.tool()
@INDICATOR_GUARD.track
def mouse_scroll(clicks: int) -> str:
    """Scroll mouse wheel vertically. Positive = scroll up, Negative = scroll down."""
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    attach_to_default_desktop()
    pyautogui.scroll(clicks)
    return json.dumps({"status": "ok", "scrolled": clicks})


@mcp.tool()
@INDICATOR_GUARD.track
def keyboard_type(text: str, interval: float = 0.02) -> str:
    """Type arbitrary text string on keyboard."""
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    attach_to_default_desktop()
    if not 0 <= interval <= 0.25:
        raise ValueError("interval debe estar entre 0 y 0.25 segundos")
    typed = 0
    for offset in range(0, len(text), 8):
        if check_user_cancelled():
            result = json.loads(cancellation_response())
            result["typed_length"] = typed
            return json.dumps(result)
        chunk = text[offset : offset + 8]
        pyautogui.write(chunk, interval=interval)
        typed += len(chunk)
    return json.dumps({"status": "ok", "typed_length": typed})


@mcp.tool()
@INDICATOR_GUARD.track
def keyboard_press_key(key: str) -> str:
    """
    Press a single key (e.g. 'enter', 'tab', 'esc', 'backspace', 'win', 'space', 'down', 'up', etc.).
    """
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    attach_to_default_desktop()
    pyautogui.press(key)
    return json.dumps({"status": "ok", "pressed_key": key})


@mcp.tool()
@INDICATOR_GUARD.track
def keyboard_hotkey(keys: List[str]) -> str:
    """
    Execute keyboard shortcut combination, e.g. ['ctrl', 'c'], ['alt', 'tab'], ['win', 'r'].
    """
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    attach_to_default_desktop()
    pyautogui.hotkey(*keys)
    return json.dumps({"status": "ok", "hotkey": keys})


@mcp.tool()
@INDICATOR_GUARD.track
def list_open_windows() -> str:
    """List titles and bounds of all visible top-level application windows on Windows desktop."""
    attach_to_default_desktop()
    windows = []
    user32 = ctypes.windll.user32

    def enum_windows_callback(hwnd, extra):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                if title.startswith("Antigravity_"):
                    return True

                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))

                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 10 and h > 10:
                    windows.append(
                        {
                            "hwnd": hwnd,
                            "title": title,
                            "left": rect.left,
                            "top": rect.top,
                            "width": w,
                            "height": h,
                            "minimized": bool(user32.IsIconic(hwnd)),
                            "foreground": hwnd == user32.GetForegroundWindow(),
                        }
                    )
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

    return json.dumps(windows, ensure_ascii=False)


@mcp.tool()
@INDICATOR_GUARD.track
def focus_window_by_title(partial_title: str = "", hwnd: Optional[int] = None) -> str:
    """Focus an existing project by title or exact hwnd. Return candidates on ambiguous titles."""
    ensure_overlay_visible()
    if check_user_cancelled():
        return cancellation_response()
    if not partial_title.strip() and hwnd is None:
        return json.dumps({"status": "error", "message": "Provide partial_title or hwnd"})
    attach_to_default_desktop()
    user32 = ctypes.windll.user32
    target_hwnd = None
    matched_title = ""
    matches = []
    requested_hwnd = hwnd

    def enum_windows_callback(hwnd, extra):
        nonlocal target_hwnd, matched_title
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                if title.startswith("Antigravity_"):
                    return True
                if (requested_hwnd is not None and hwnd == requested_hwnd) or (
                    requested_hwnd is None and partial_title.casefold() in title.casefold()
                ):
                    target_hwnd = hwnd
                    matched_title = title
                    matches.append({"hwnd": hwnd, "title": title})
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

    if len(matches) > 1:
        return json.dumps(
            {
                "status": "ambiguous",
                "message": "Choose a project window by hwnd",
                "windows": matches,
            },
            ensure_ascii=False,
        )
    if target_hwnd:
        cur_fg = user32.GetForegroundWindow()
        cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        fg_thread = user32.GetWindowThreadProcessId(cur_fg, None)
        target_thread = user32.GetWindowThreadProcessId(target_hwnd, None)

        attached = []
        try:
            for source, target in {(cur_thread, target_thread), (fg_thread, target_thread)}:
                if (
                    source
                    and target
                    and source != target
                    and user32.AttachThreadInput(source, target, True)
                ):
                    attached.append((source, target))
            if user32.IsIconic(target_hwnd):
                user32.ShowWindow(target_hwnd, 9)  # Preserve maximized windows.
            user32.BringWindowToTop(target_hwnd)
            user32.SetForegroundWindow(target_hwnd)
        finally:
            for source, target in attached:
                user32.AttachThreadInput(source, target, False)
        focused = user32.GetForegroundWindow() == target_hwnd
        return json.dumps(
            {
                "status": "focused" if focused else "focus_denied",
                "matched_title": matched_title,
                "hwnd": target_hwnd,
            }
        )
    else:
        return json.dumps(
            {"status": "error", "message": f"No visible window found matching '{partial_title}'"}
        )


def main():
    """Serve MCP over stdio; imports and tests never modify runtime state."""
    atexit.register(hide_screen_overlay)
    attach_to_default_desktop()
    INDICATOR_GUARD.start()
    try:
        mcp.run(transport="stdio")
    finally:
        INDICATOR_GUARD.stop()
        hide_screen_overlay()


if __name__ == "__main__":
    main()
