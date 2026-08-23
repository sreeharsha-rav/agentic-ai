"""Enables `python -m meeting_pipeline_2`.

Port reference: `meeting_pipeline/__main__.py`.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
