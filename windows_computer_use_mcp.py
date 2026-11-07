"""Compatibility launcher for existing Antigravity MCP configurations."""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from windows_computer_use.server import main

    main()
