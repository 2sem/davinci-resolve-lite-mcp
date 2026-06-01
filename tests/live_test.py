#!/usr/bin/env python
"""Live integration test entrypoint."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.live import main


if __name__ == "__main__":
    sys.exit(main(sys.argv))
