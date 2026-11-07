import json
import time

from windows_computer_use import demo_capture


def test_recording_marker_requires_explicit_opt_in_and_expires(tmp_path, monkeypatch):
    marker = tmp_path / "recording.json"
    monkeypatch.delenv("WINDOWS_COMPUTER_USE_DEMO_CAPTURE", raising=False)
    monkeypatch.setattr(demo_capture, "marker_path", lambda: marker)
    assert not demo_capture.demo_capture_enabled()
    marker.write_text(json.dumps({"include_indicator": True, "expires_at": time.time() + 60}))
    assert demo_capture.demo_capture_enabled()
    marker.write_text(json.dumps({"include_indicator": True, "expires_at": time.time() - 1}))
    assert not demo_capture.demo_capture_enabled()
    marker.write_text("{broken")
    assert not demo_capture.demo_capture_enabled()
