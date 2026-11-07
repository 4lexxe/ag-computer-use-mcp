"""Fast desktop capture with explicit preview-to-desktop coordinates."""

import io
import threading
import time

import mss
from PIL import Image

_local = threading.local()


def capture_screen(max_dimension=1600, quality=80, monitor=1, region=None, save_path=None):
    if max_dimension is not None and max_dimension < 64:
        raise ValueError("max_dimension must be at least 64, or null for full resolution")
    if not 40 <= quality <= 95:
        raise ValueError("quality must be between 40 and 95")
    started = time.perf_counter()
    if not hasattr(_local, "capture") or time.monotonic() - _local.created > 5:
        if hasattr(_local, "capture"):
            _local.capture.close()
        _local.capture = mss.MSS()
        _local.created = time.monotonic()
    sct = _local.capture
    monitors = sct.monitors
    if monitor < 0 or monitor >= len(monitors):
        raise ValueError(f"monitor must be between 0 and {len(monitors) - 1}; 0 = entire desktop")
    bounds = dict(monitors[monitor])
    if region is not None:
        if len(region) != 4:
            raise ValueError("region must be [left, top, width, height] in desktop pixels")
        left, top, width, height = region
        desktop = monitors[0]
        if (
            width <= 0
            or height <= 0
            or left < desktop["left"]
            or top < desktop["top"]
            or left + width > desktop["left"] + desktop["width"]
            or top + height > desktop["top"] + desktop["height"]
        ):
            raise ValueError("region must be inside the virtual desktop")
        bounds = dict(left=left, top=top, width=width, height=height)
    shot = sct.grab(bounds)
    image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if save_path:
        from pathlib import Path

        path = Path(save_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    original_width, original_height = image.size
    if max_dimension and max(image.size) > max_dimension:
        scale = max_dimension / max(image.size)
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.BILINEAR,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    payload = buffer.getvalue()
    metadata = dict(
        original_width=original_width,
        original_height=original_height,
        preview_width=image.width,
        preview_height=image.height,
        origin_x=bounds["left"],
        origin_y=bounds["top"],
        scale_x=original_width / image.width,
        scale_y=original_height / image.height,
        monitor=monitor,
        saved_path=save_path,
        encoded_bytes=len(payload),
        capture_ms=round((time.perf_counter() - started) * 1000, 1),
        coordinate_formula="desktop_x = origin_x + preview_x * scale_x; desktop_y = origin_y + preview_y * scale_y",
    )
    return metadata, payload
