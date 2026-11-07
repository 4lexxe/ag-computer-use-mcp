"""Compatibility launcher; prefer windows-computer-use-preview --preview."""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from windows_computer_use.overlay import main

    main()
