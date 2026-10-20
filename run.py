"""Quick CLI runner entrypoint (`python run.py`)."""

from __future__ import annotations

import sys

from draftproof.cli import main

if __name__ == "__main__":
    sys.exit(main())
