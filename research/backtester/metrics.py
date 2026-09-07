"""Metric calculation. Python owns these numbers exclusively.

AGENTS.md: *"AI never computes authoritative metrics. Python does. Never restate a
number the backtester did not produce."*

Deliberate design choices:

- ``sharpe`` returns None below a minimum trade count rather than a flattering number
  computed from noise. §18 expects the system to flag "17 trades, Sharpe 4.8", not
  celebrate it.
- cost breakdown (fees / funding / slippage) is reported separately from gross P&L so
  the critic can see how much edge the costs ate.
- warnings are emitted by the engine itself: low trade count, single-period
  concentration, one-trade-dominates. The report agent may not suppress them.
"""

from __future__ import annotations

#: Below this, risk-adjusted ratios are not reported (they would be noise).
MIN_TRADES_FOR_RATIOS = 30


def calculate(trades: object, equity_curve: object) -> dict:
    raise NotImplementedError("Experiment 003 / Week 7-8")
