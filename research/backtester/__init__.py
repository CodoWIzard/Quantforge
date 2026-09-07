"""Deterministic backtest engine.

Blueprint §21. The engine must produce identical output for identical inputs - that is
what makes a RunManifest meaningful. No randomness without a recorded seed, no wall
clock, no network calls during a run.
"""

from .engine import run
from .lookahead import assert_no_lookahead

__all__ = ["run", "assert_no_lookahead"]
