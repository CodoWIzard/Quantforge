"""Aggregate the battery into PASS / CAUTION / FAIL (§9 step 7).

The user sees a verdict *with evidence*, never a single return number. Aggregation is
deterministic and conservative:

- any FAIL in the battery         -> FAIL
- any CAUTION, or thin evidence   -> CAUTION
- all PASS with adequate sample   -> PASS

The critic agent may argue about interpretation. It cannot change this arithmetic.
"""

from __future__ import annotations


def aggregate(test_results: list[dict]) -> str:
    raise NotImplementedError("Week 11-12: validation")
