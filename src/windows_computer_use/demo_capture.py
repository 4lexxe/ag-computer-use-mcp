"""Explicit, expiring opt-in to include this indicator in a locally recorded demo."""

import json
import os
import time
from pathlib import Path


def marker_path():
    return Path(__file__).resolve().parents[2] / ".local" / "demo-recording.json"


def demo_capture_enabled():
    if os.environ.get("WINDOWS_COMPUTER_USE_DEMO_CAPTURE") == "1":
        return True
    try:
        marker = json.loads(marker_path().read_text(encoding="utf-8"))
        return marker.get("include_indicator") is True and time.time() < float(marker["expires_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
