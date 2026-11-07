"""pywinauto UIA integration, isolated in a short-lived worker with a hard timeout."""

import contextlib
import json
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path

_snapshots = {}
_lock = threading.RLock()
SNAPSHOT_TTL = 30


def worker_request(request):
    try:
        process = subprocess.run(
            [sys.executable, "-m", "windows_computer_use.accessibility"],
            input=json.dumps(request),
            encoding="utf-8",
            capture_output=True,
            cwd=Path(__file__).resolve().parent.parent,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "code": "ACCESSIBILITY_TIMEOUT",
            "error": "La aplicación no respondió a accesibilidad en 8 segundos. Usa read_screen.",
        }
    if process.returncode:
        return {
            "status": "error",
            "code": "ACCESSIBILITY_UNAVAILABLE",
            "error": "No se pudo consultar UI Automation. Usa read_screen para esta ventana.",
        }
    try:
        return json.loads(process.stdout)
    except ValueError:
        return {"status": "error", "code": "INVALID_ACCESSIBILITY_RESPONSE"}


def inspect(hwnd, max_elements=120, depth=5):
    if hwnd <= 0 or not 1 <= max_elements <= 250 or not 1 <= depth <= 8:
        return {
            "status": "error",
            "error": "hwnd debe ser positivo; max_elements 1..250; depth 1..8",
        }
    result = worker_request(
        dict(action="inspect", hwnd=hwnd, max_elements=max_elements, depth=depth)
    )
    if result.get("status") == "ok":
        token = uuid.uuid4().hex
        with _lock:
            now = time.monotonic()
            for expired in [
                key for key, value in _snapshots.items() if now - value["created"] > SNAPSHOT_TTL
            ]:
                del _snapshots[expired]
            if len(_snapshots) >= 32:
                del _snapshots[next(iter(_snapshots))]
            _snapshots[token] = {"created": now, "hwnd": hwnd, "result": result, "depth": depth}
        result = {
            **result,
            "snapshot_id": token,
            "expires_in_seconds": SNAPSHOT_TTL,
            "next_step": "Usa invoke_control con este snapshot_id y un element_id; vuelve a inspeccionar después de cambiar la interfaz.",
        }
    return result


def invoke(hwnd, snapshot_id, element_id):
    with _lock:
        snapshot = _snapshots.get(snapshot_id)
    if (
        not snapshot
        or snapshot["hwnd"] != hwnd
        or time.monotonic() - snapshot["created"] > SNAPSHOT_TTL
    ):
        return {
            "status": "error",
            "code": "STALE_SNAPSHOT",
            "error": "Vuelve a ejecutar inspect_window.",
        }
    matches = [item for item in snapshot["result"]["elements"] if item["element_id"] == element_id]
    if len(matches) != 1:
        return {
            "status": "error",
            "code": "UNKNOWN_ELEMENT",
            "error": "Selecciona un element_id del último inspect_window.",
        }
    request = dict(
        action="invoke",
        hwnd=hwnd,
        expected=matches[0],
        process_id=snapshot["result"]["process_id"],
        depth=snapshot["depth"],
    )
    # Consume before launching so simultaneous retries cannot invoke twice.
    with _lock:
        if _snapshots.pop(snapshot_id, None) is None:
            return {"status": "error", "code": "STALE_SNAPSHOT"}
    return worker_request(request)


def describe(control):
    info = control.element_info
    try:
        protected = bool(info.element.CurrentIsPassword)
    except (AttributeError, OSError):
        protected = False
    rectangle = control.rectangle()
    return {
        "element_id": ":".join(str(value) for value in info.runtime_id),
        "name": "[campo protegido]" if protected else str(info.name or "")[:300],
        "control_type": info.control_type,
        "automation_id": info.automation_id,
        "enabled": control.is_enabled(),
        "visible": control.is_visible(),
        "protected": protected,
        "bounds": [rectangle.left, rectangle.top, rectangle.right, rectangle.bottom],
    }


def walk_controls(root, depth):
    queue = deque([(root, 0)])
    while queue:
        control, level = queue.popleft()
        yield control
        if level < depth:
            queue.extend((child, level + 1) for child in control.children())


def run_worker(request, desktop=None):
    if desktop is None:
        # Initialize COM only inside this process/thread, not MCP worker threads.
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
    root = desktop.window(handle=request["hwnd"]).wrapper_object()
    if root.window_text().startswith("Antigravity_"):
        return {"status": "error", "code": "CONTROL_INDICATOR_EXCLUDED"}
    if request["action"] == "inspect":
        elements = []
        truncated = False
        for control in walk_controls(root, request["depth"]):
            if len(elements) >= request["max_elements"]:
                truncated = True
                break
            try:
                item = describe(control)
                if item["visible"]:
                    elements.append(item)
            except Exception:
                continue  # Dynamic UIA elements can disappear during enumeration.
        return {
            "status": "ok",
            "backend": "pywinauto/uia",
            "hwnd": request["hwnd"],
            "process_id": root.element_info.process_id,
            "title": root.window_text(),
            "elements": elements,
            "truncated": truncated,
        }
    if root.element_info.process_id != request["process_id"]:
        return {"status": "error", "code": "STALE_WINDOW"}
    expected = request["expected"]
    for index, control in enumerate(walk_controls(root, request["depth"])):
        if index >= 1000:
            break
        item = describe(control)
        if item["element_id"] != expected["element_id"]:
            continue
        if any(item[key] != expected[key] for key in ("name", "automation_id", "control_type")):
            return {"status": "error", "code": "ELEMENT_CHANGED"}
        if not item["enabled"] or not item["visible"] or item["protected"]:
            return {"status": "error", "code": "ELEMENT_NOT_AVAILABLE"}
        from .session_state import read_status

        if read_status()["status"] != "active":
            return {"status": "aborted", "code": "SCREEN_SESSION_STOPPED"}
        # Invoke is semantic: never silently fall back to an unverified pixel click.
        control.invoke()
        return {"status": "ok", "invoked": item["element_id"], "refresh_required": True}
    return {"status": "error", "code": "ELEMENT_DISAPPEARED"}


def main():
    request = json.load(sys.stdin)
    try:
        # Keep stdout protocol-clean even if a third-party library logs on import.
        with contextlib.redirect_stdout(sys.stderr):
            result = run_worker(request)
    except Exception:
        result = {
            "status": "error",
            "code": "ACCESSIBILITY_PROVIDER_ERROR",
            "error": "El control no expone la operación solicitada o cambió. Vuelve a inspeccionar o usa read_screen.",
        }
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
