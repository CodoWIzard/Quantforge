"""Do live simulated fills differ materially from historical assumptions?

Compare paper-execution fills and signal timing against what the backtest assumed.

This is the only test that can falsify the backtest with reality, so it runs
continuously once a strategy is deployed to paper - not once.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
