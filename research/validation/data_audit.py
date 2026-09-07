"""Is the dataset complete, correctly timestamped and appropriate?

Coverage, gap and duplicate report over the exact partitions in the RunManifest.

A detected gap must either fail the run or be explicitly marked and excluded - the
``gap_policy`` field. §18 names silent interpolation as a failure case.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
