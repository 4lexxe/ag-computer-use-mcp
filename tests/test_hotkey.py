import ctypes
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import Mock

from windows_computer_use import hotkey


def test_shortcut_is_delivered_as_a_windows_message_without_polling(monkeypatch):
    delivered = False

    def get_message(pointer, hwnd, first, last):
        nonlocal delivered
        if delivered:
            return 0
        message = ctypes.cast(pointer, ctypes.POINTER(wintypes.MSG)).contents
        message.message = 0x0312
        message.wParam = hotkey.GlobalStopHotkey.HOTKEY_ID
        delivered = True
        return 1

    user32 = SimpleNamespace(
        RegisterHotKey=Mock(return_value=True),
        UnregisterHotKey=Mock(return_value=True),
        GetMessageW=Mock(side_effect=get_message),
    )
    monkeypatch.setattr(ctypes.windll, "user32", user32)
    monkeypatch.setattr(
        ctypes.windll, "kernel32", SimpleNamespace(GetCurrentThreadId=Mock(return_value=123))
    )

    class ImmediateThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            self.target()

        def is_alive(self):
            return False

    monkeypatch.setattr(hotkey.threading, "Thread", ImmediateThread)
    listener = hotkey.GlobalStopHotkey()
    assert listener.registered
    assert listener.triggered.is_set()
    user32.RegisterHotKey.assert_called_once_with(None, listener.HOTKEY_ID, 0x4003, 0x1B)
    user32.UnregisterHotKey.assert_called_once_with(None, listener.HOTKEY_ID)
    listener.close()
