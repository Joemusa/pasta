"""CLI: python -m backend.dashboard"""

from __future__ import annotations

import sys

from backend.dashboard.server import main

if __name__ == "__main__":
    sys.exit(main())
