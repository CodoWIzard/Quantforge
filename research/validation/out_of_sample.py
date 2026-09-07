"""Does performance survive periods not used to select the rules?

Walk-forward: repeated train/selection windows followed by untouched test windows.

The selection window is where overfitting happens; the test window is the only honest
number. Report both, never only the combined figure.

Blueprint §23.
"""

from __future__ import annotations


def run(result: object, manifest: object) -> dict:
    """Return {"name", "outcome": pass|caution|fail, "detail"}."""
    raise NotImplementedError("Week 11-12: validation")
