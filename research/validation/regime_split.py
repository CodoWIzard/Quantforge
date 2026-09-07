"""Is the strategy only profitable in one regime?

Partition by volatility, trend direction and known crisis windows.

A strategy that made all its money in one three-week window is a story about that
window, not a strategy.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
