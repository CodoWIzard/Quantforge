"""Is the result dominated by a handful of trades?

Contribution of the top-N trades and the longest flat period.

If removing the best three trades removes the profit, the sample proves nothing.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
