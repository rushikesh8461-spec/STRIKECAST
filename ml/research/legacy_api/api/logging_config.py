"""
Application logging setup.

Keeps logging simple, structured enough to be useful, and careful never to
log secrets or full stack traces to API consumers (that happens only in the
server-side logs, never in HTTP responses - see main.py exception handlers).
"""
from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    root = logging.getLogger("strikecast")
    if root.handlers:
        # Already configured (e.g. re-imported in tests) - avoid duplicate handlers.
        root.setLevel(level.upper())
        return root

    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.propagate = False
    return root


logger = setup_logging()
