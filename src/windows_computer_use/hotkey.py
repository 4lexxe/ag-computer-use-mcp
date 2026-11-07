"""Global stop shortcut delivered by Windows, including very short key presses."""

import ctypes
import threading
from ctypes import wintypes


class GlobalStopHotkey:
    HOTKEY_ID = 0xA617

    def __init__(self):
        self.triggered = threading.Event()
        self.started = threading.Event()
        self.registered = False
        self.thread_id = None
        self.thread = threading.Thread(target=self._listen, name="screen-stop-hotkey", daemon=True)
        self.thread.start()
        self.started.wait(1)

    def _listen(self):
        user32, kernel = ctypes.windll.user32, ctypes.windll.kernel32
        kernel.GetCurrentThreadId.restype = wintypes.DWORD
        self.thread_id = kernel.GetCurrentThreadId()
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        self.registered = bool(user32.RegisterHotKey(None, self.HOTKEY_ID, 0x4003, 0x1B))
        self.started.set()
        if not self.registered:
            return
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam == self.HOTKEY_ID:
                    self.triggered.set()
        finally:
            user32.UnregisterHotKey(None, self.HOTKEY_ID)

    def close(self):
        if self.thread_id and self.thread.is_alive():
            user32 = ctypes.windll.user32
            user32.PostThreadMessageW.argtypes = [
                wintypes.DWORD,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
            self.thread.join(1)
