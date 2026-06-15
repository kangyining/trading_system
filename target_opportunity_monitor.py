"""Root shim for running the src-layout package without installation.

This allows:

    python -m target_opportunity_monitor status

from the project root during early local development.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    sys.path.insert(0, str(src_path))
    runpy.run_module("target_opportunity_monitor", run_name="__main__")


if __name__ == "__main__":
    main()

