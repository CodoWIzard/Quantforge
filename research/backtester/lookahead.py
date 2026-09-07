"""No-look-ahead assertions.

§23: *"Did any feature or entry use information that would not have been known at the
time?"* This is the single most common way a backtest lies, so it is a hard assertion
inside the engine, not an optional test.

Checks:

- every signal index >= the rule's declared ``lookback_bars``
- entry fills use the bar *after* the signal when ``execute_at`` is ``next_bar_open``
- no indicator column is computed with a centred or forward-shifted window
- stop/target resolution within a bar follows a declared priority policy rather than
  picking whichever is favourable
"""

from __future__ import annotations


def assert_no_lookahead(result: object) -> None:
    """Raise if any signal could not have been known at its own timestamp."""
    raise NotImplementedError("Experiment 003 / Week 7-8")
