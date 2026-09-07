"""Is the result fragile to trade order and noise?

Resample the trade sequence to build a distribution around the observed result.

Answers "could this have happened by luck?" with a distribution rather than a point.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
