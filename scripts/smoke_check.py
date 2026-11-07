"""Verify the real stdio MCP connection without controlling the desktop."""

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "inspect_window",
    "invoke_control",
    "show_screen_overlay",
    "hide_screen_overlay",
    "resume_screen_control",
    "get_control_status",
    "read_screen",
    "take_screenshot",
    "list_open_windows",
    "focus_window_by_title",
    "get_screen_resolution",
    "mouse_move",
    "mouse_click",
    "mouse_drag",
    "mouse_scroll",
    "keyboard_type",
    "keyboard_press_key",
    "keyboard_hotkey",
}


async def check(python, installed):
    with tempfile.TemporaryDirectory(prefix="windows-mcp-check-") as temporary:
        environment = dict(os.environ)
        environment["WINDOWS_COMPUTER_USE_STATE_DIR"] = str(Path(temporary) / "state")
        arguments = (
            ["-m", "windows_computer_use"]
            if installed
            else [str(ROOT / "windows_computer_use_mcp.py")]
        )
        server = StdioServerParameters(
            command=python, args=arguments, env=environment, cwd=temporary
        )
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=15) as session:
                await session.initialize()
                listing = await session.list_tools()
                actual = {tool.name for tool in listing.tools}
                missing = EXPECTED_TOOLS - actual
                if missing:
                    raise RuntimeError(f"Missing tools: {sorted(missing)}")
                result = await session.call_tool("get_control_status", {})
                if result.is_error:
                    raise RuntimeError("get_control_status returned an error")
                state = json.loads(result.content[0].text)
                if state["status"] != "close" or state["overlay_running"]:
                    raise RuntimeError(f"Unexpected initial state: {state}")
        print(f"MCP stdio OK: {len(actual)} tools, isolated state, unrelated working directory.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to verify")
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Verify the installed module instead of the legacy launcher",
    )
    args = parser.parse_args()
    asyncio.run(check(args.python, args.installed))


if __name__ == "__main__":
    main()
