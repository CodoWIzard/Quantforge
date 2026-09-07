"""Does a tiny threshold change destroy the result?

Sweep each parameter through a neighbourhood and map the performance surface.

A sharp isolated peak is overfitting. A broad plateau is a possible edge. The shape
matters more than the maximum.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
