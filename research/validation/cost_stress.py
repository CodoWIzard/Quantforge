"""Does the edge survive realistic fees, spread, slippage and funding?

Re-run at progressively worse cost assumptions and report where the edge dies.

An edge that only exists at zero fees is not an edge. Report the break-even cost level,
not just pass/fail - it tells the user how much margin they actually have.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
