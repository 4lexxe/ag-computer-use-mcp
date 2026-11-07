"""Antigravity indicator: native translucent edge animation and a separate stop bar."""

import ctypes
import os
import sys
import time
import tkinter as tk
from ctypes import wintypes

from PIL import ImageTk

from .antigravity_lifecycle import AntigravityRunMonitor
from .demo_capture import demo_capture_enabled
from .hotkey import GlobalStopHotkey
from .layered_window import LayeredSurface, keep_topmost
from .overlay_visuals import (
    BORDER_WIDTH,
    FRAME_MS,
    HEADLINE,
    PULSE_GROWTH,
    CursorAnimation,
    EdgeAnimation,
    brand_image,
    subtitle,
)
from .session_state import close_if_not_cancelled, read_status, write_status

BACKGROUND = "#191c25"


def configure_window(window, click_through=False):
    user32 = ctypes.windll.user32
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    preview = "--preview" in sys.argv
    style = user32.GetWindowLongW(hwnd, -20) | 0x80 | 0x08000000
    if preview:
        style = (style & ~0x80) | 0x40000
    if click_through:
        style |= 0x20 | 0x80000
    user32.SetWindowLongW(hwnd, -20, style)
    if hasattr(user32, "SetWindowDisplayAffinity"):
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity(hwnd, 0 if preview or demo_capture_enabled() else 0x11)
    return hwnd


def monitor_bounds():
    bounds = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
    )

    def collect(handle, dc, rect, data):
        r = rect.contents
        bounds.append((r.left, r.top, r.right, r.bottom))
        return True

    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_type(collect), 0)
    return bounds


def parent_is_alive(pid):
    if not pid:
        return True
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT = alive
    finally:
        kernel.CloseHandle(handle)


def square_window(hwnd):
    """Disable Windows 11 automatic corner rounding; ignored on older Windows."""
    preference = ctypes.c_int(1)
    try:
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
    except (AttributeError, OSError):
        pass


def create_glow_overlay():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        pass
    root = tk.Tk()
    root.withdraw()
    scale = min(3.0, max(0.75, root.winfo_fpixels("1i") / 96))

    def px(value):
        return max(1, round(value * scale))

    icon = ImageTk.PhotoImage(brand_image("gemini", px(48)), master=root)
    root.iconphoto(True, icon)
    windows, animations, surfaces = [], [], []
    bounds = monitor_bounds()
    if not bounds:
        root.destroy()
        return
    parent_pid = int(os.environ.get("WINDOWS_COMPUTER_USE_PARENT_PID", "0"))
    run_monitor = AntigravityRunMonitor()
    stop_hotkey = GlobalStopHotkey()

    for monitor_index, (left, top, right, bottom) in enumerate(bounds):
        animation = EdgeAnimation(right - left, bottom - top, scale, seed=monitor_index)
        group = []
        for edge_index, (x1, y1, x2, y2) in enumerate(animation.boxes):
            if x2 <= x1 or y2 <= y1:
                continue
            window = tk.Toplevel(root)
            window.withdraw()
            window.title(f"Antigravity_Computer_Use_Overlay:{monitor_index}:{edge_index}")
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.geometry(f"{x2 - x1}x{y2 - y1}+0+0")
            window.update_idletasks()
            hwnd = configure_window(window, click_through=True)
            window.deiconify()
            surface = LayeredSurface(hwnd, left + x1, top + y1, x2 - x1, y2 - y1)
            surface.paint(animation.backgrounds[edge_index])
            group.append(surface)
            surfaces.append(surface)
            windows.append(window)
        animations.append((animation, group))

    banner = tk.Toplevel(root)
    banner.withdraw()
    banner.title("Antigravity_Control")
    banner.overrideredirect(True)
    banner.configure(bg=BACKGROUND)
    banner.attributes("-alpha", 0.89)
    banner.attributes("-topmost", True)
    primary = next((b for b in bounds if b[0] == 0 and b[1] == 0), bounds[0])
    width, height = min(px(680), primary[2] - primary[0] - px(32)), px(68)
    x = primary[0] + (primary[2] - primary[0] - width) // 2
    banner.geometry(f"{width}x{height}{x:+d}{primary[1] + px(BORDER_WIDTH + PULSE_GROWTH + 16):+d}")
    outline = tk.Frame(banner, bg=BACKGROUND, highlightbackground="#41495a", highlightthickness=1)
    outline.pack(fill="both", expand=True)
    body = tk.Frame(outline, bg=BACKGROUND)
    body.pack(fill="both", expand=True, padx=px(18), pady=px(10))
    logo = ImageTk.PhotoImage(brand_image("antigravity", px(34)), master=root)
    tk.Label(body, image=logo, bg=BACKGROUND).pack(side="left", padx=(0, px(12)))
    text = tk.Frame(body, bg=BACKGROUND)
    text.pack(side="left", fill="x", expand=True)
    tk.Label(
        text,
        text=HEADLINE,
        anchor="w",
        bg=BACKGROUND,
        fg="#f4f5fa",
        font=("Segoe UI Semibold", -px(15 if width >= px(620) else 13)),
    ).pack(fill="x")
    detail = tk.Label(
        text,
        text="Listo para continuar",
        anchor="w",
        bg=BACKGROUND,
        fg="#b3bacb",
        font=("Segoe UI", -px(11)),
    )
    detail.pack(fill="x", pady=(px(3), 0))
    gemini = ImageTk.PhotoImage(brand_image("gemini", px(20)), master=root)
    provider = tk.Label(
        body,
        image=gemini,
        text=" Gemini",
        compound="left",
        fg="#cbd1df",
        bg=BACKGROUND,
        font=("Segoe UI", -px(11)),
    )
    if width >= px(620):
        provider.pack(side="left", padx=px(14))
    tk.Frame(body, width=1, bg="#3a404e").pack(
        side="left", fill="y", padx=(px(6), px(14)), pady=px(4)
    )
    stop_frame = tk.Frame(body, bg=BACKGROUND)
    stop_frame.pack(side="right")

    def cancel():
        write_status("cancelled")
        root.destroy()

    stop = tk.Button(
        stop_frame,
        text="■  Detener",
        command=cancel,
        bg="#363d4c",
        fg="#ffffff",
        activebackground="#be4059",
        activeforeground="#ffffff",
        font=("Segoe UI Semibold", -px(12)),
        bd=0,
        padx=px(12),
        pady=px(5),
        cursor="hand2",
        takefocus=False,
    )
    stop.pack()
    stop.bind("<Enter>", lambda event: stop.configure(bg="#be4059"))
    stop.bind("<Leave>", lambda event: stop.configure(bg="#363d4c"))
    tk.Label(
        stop_frame,
        text="Ctrl+Alt+Esc" if stop_hotkey.registered else "Atajo ocupado",
        fg="#9099ae",
        bg=BACKGROUND,
        font=("Segoe UI", -px(9)),
    ).pack(pady=(px(2), 0))
    banner.update_idletasks()
    hwnd = configure_window(banner)
    banner_hwnd = hwnd
    square_window(banner_hwnd)
    banner.deiconify()
    cursor_animation = CursorAnimation(scale)
    cursor_window = tk.Toplevel(root)
    cursor_window.withdraw()
    cursor_window.title("Antigravity_Cursor")
    cursor_window.overrideredirect(True)
    cursor_window.attributes("-topmost", True)
    cursor_window.geometry(f"{cursor_animation.size}x{cursor_animation.size}+0+0")
    cursor_window.update_idletasks()
    cursor_hwnd = configure_window(cursor_window, click_through=True)
    cursor_window.deiconify()
    cursor_surface = LayeredSurface(cursor_hwnd, 0, 0, cursor_animation.size, cursor_animation.size)
    surfaces.append(cursor_surface)
    windows.append(cursor_window)
    # Keep image objects alive for Tk's image registry.
    root.brand_images = (icon, logo, gemini)
    key_state = ctypes.windll.user32.GetAsyncKeyState
    key_state.argtypes, key_state.restype = [ctypes.c_int], ctypes.c_short
    user32 = ctypes.windll.user32
    user32.GetCursorPos.argtypes, user32.GetCursorPos.restype = (
        [ctypes.POINTER(wintypes.POINT)],
        wintypes.BOOL,
    )
    user32.GetForegroundWindow.argtypes, user32.GetForegroundWindow.restype = [], wintypes.HWND
    last_parent_check = 0.0
    last_zorder_refresh, last_foreground = 0.0, None
    last_capture_check = 0.0
    last_run_check = 0.0
    capture_visible = "--preview" in sys.argv or demo_capture_enabled()

    def cursor_tick():
        point = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(point)):
            now = time.monotonic()
            pressed = bool(key_state(0x01) & 0x8000 or key_state(0x02) & 0x8000)
            cursor_surface.position.x = point.x - cursor_animation.center
            cursor_surface.position.y = point.y - cursor_animation.center
            cursor_surface.paint(cursor_animation.frame(point.x, point.y, now, pressed))
        root.after(16, cursor_tick)

    def tick():
        nonlocal \
            last_parent_check, \
            last_zorder_refresh, \
            last_foreground, \
            last_capture_check, \
            last_run_check, \
            capture_visible
        state = read_status()
        if state["status"] in ("close", "cancelled"):
            root.destroy()
            return
        if stop_hotkey.triggered.is_set() or all(
            key_state(key) & 0x8000 for key in (0x11, 0x12, 0x1B)
        ):
            cancel()
            return
        now = time.monotonic()
        if now - last_run_check >= 0.5:
            last_run_check = now
            if run_monitor.finished():
                close_if_not_cancelled()
                root.destroy()
                return
        if now - last_capture_check >= 1:
            last_capture_check = now
            visible = "--preview" in sys.argv or demo_capture_enabled()
            if visible != capture_visible and hasattr(user32, "SetWindowDisplayAffinity"):
                for window_handle in [surface.hwnd for surface in surfaces] + [banner_hwnd]:
                    user32.SetWindowDisplayAffinity(window_handle, 0 if visible else 0x11)
                capture_visible = visible
        foreground = user32.GetForegroundWindow()
        if foreground != last_foreground or now - last_zorder_refresh >= 0.2:
            keep_topmost([surface.hwnd for surface in surfaces] + [banner_hwnd])
            last_zorder_refresh, last_foreground = now, foreground
        if parent_pid and now - last_parent_check >= 1:
            last_parent_check = now
            if not parent_is_alive(parent_pid):
                root.destroy()
                return
        detail.configure(text=subtitle(state))
        for animation, group in animations:
            for surface, frame in zip(group, animation.frames(now)):
                surface.paint(frame)
        root.after(FRAME_MS, tick)

    try:
        root.after(0, tick)
        root.after(0, cursor_tick)
        root.mainloop()
    finally:
        stop_hotkey.close()
        for surface in surfaces:
            surface.close()


def main():
    if "--preview" in sys.argv:
        write_status("active", "Vista previa", activity="reading")
    create_glow_overlay()


if __name__ == "__main__":
    main()
