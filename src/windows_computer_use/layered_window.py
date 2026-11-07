"""Per-pixel alpha surfaces with persistent GDI buffers (no full-screen frame copies)."""

import ctypes
from ctypes import wintypes


class Size(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class Blend(ctypes.Structure):
    _fields_ = [
        ("op", ctypes.c_ubyte),
        ("flags", ctypes.c_ubyte),
        ("alpha", ctypes.c_ubyte),
        ("format", ctypes.c_ubyte),
    ]


class BitmapHeader(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("width", ctypes.c_long),
        ("height", ctypes.c_long),
        ("planes", wintypes.WORD),
        ("bits", wintypes.WORD),
        ("compression", wintypes.DWORD),
        ("image_size", wintypes.DWORD),
        ("xppm", ctypes.c_long),
        ("yppm", ctypes.c_long),
        ("colors", wintypes.DWORD),
        ("important", wintypes.DWORD),
    ]


class LayeredSurface:
    def __init__(self, hwnd, x, y, width, height):
        self.hwnd, self.position, self.size = hwnd, wintypes.POINT(x, y), Size(width, height)
        self.user32, self.gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        u, g = self.user32, self.gdi32
        u.GetDC.argtypes, u.GetDC.restype = [wintypes.HWND], wintypes.HDC
        u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        g.CreateCompatibleDC.argtypes, g.CreateCompatibleDC.restype = [wintypes.HDC], wintypes.HDC
        g.CreateDIBSection.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(BitmapHeader),
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        g.CreateDIBSection.restype = wintypes.HANDLE
        g.SelectObject.argtypes, g.SelectObject.restype = (
            [wintypes.HDC, wintypes.HANDLE],
            wintypes.HANDLE,
        )
        g.DeleteObject.argtypes = [wintypes.HANDLE]
        g.DeleteDC.argtypes = [wintypes.HDC]
        u.UpdateLayeredWindow.argtypes = [
            wintypes.HWND,
            wintypes.HDC,
            ctypes.POINTER(wintypes.POINT),
            ctypes.POINTER(Size),
            wintypes.HDC,
            ctypes.POINTER(wintypes.POINT),
            wintypes.DWORD,
            ctypes.POINTER(Blend),
            wintypes.DWORD,
        ]
        u.UpdateLayeredWindow.restype = wintypes.BOOL
        screen = u.GetDC(None)
        self.dc = g.CreateCompatibleDC(screen)
        header = BitmapHeader(
            ctypes.sizeof(BitmapHeader), width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0
        )
        self.pixels = ctypes.c_void_p()
        self.bitmap = g.CreateDIBSection(
            screen, ctypes.byref(header), 0, ctypes.byref(self.pixels), None, 0
        )
        u.ReleaseDC(None, screen)
        if not self.dc or not self.bitmap or not self.pixels.value:
            self.close()
            raise OSError("Unable to allocate the translucent indicator surface")
        self.previous = g.SelectObject(self.dc, self.bitmap)

    def paint(self, image):
        # Windows requires premultiplied BGRA for true per-pixel transparency.
        pixels = image.convert("RGBa").tobytes("raw", "BGRa")
        ctypes.memmove(self.pixels, pixels, len(pixels))
        source, blend = wintypes.POINT(0, 0), Blend(0, 0, 255, 1)
        if not self.user32.UpdateLayeredWindow(
            self.hwnd,
            None,
            ctypes.byref(self.position),
            ctypes.byref(self.size),
            self.dc,
            ctypes.byref(source),
            0,
            ctypes.byref(blend),
            2,
        ):
            raise OSError("Unable to update the translucent indicator surface")

    def close(self):
        if getattr(self, "previous", None):
            self.gdi32.SelectObject(self.dc, self.previous)
            self.previous = None
        if getattr(self, "bitmap", None):
            self.gdi32.DeleteObject(self.bitmap)
            self.bitmap = None
        if getattr(self, "dc", None):
            self.gdi32.DeleteDC(self.dc)
            self.dc = None


def keep_topmost(handles):
    """Refresh z-order above ordinary topmost windows without moving or activating."""
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    flags = 0x0001 | 0x0002 | 0x0010 | 0x0200 | 0x0400
    for hwnd in handles:
        user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, flags)
