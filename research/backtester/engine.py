"""The eight-step run (§21).

    1. validate StrategySpec          - invalid spec cannot proceed
    2. resolve immutable inputs       - build the RunManifest
    3. load historical data           - only the needed Parquet partitions
    4. calculate signals              - t may only use information at or before t
    5. simulate orders                - entry timing, slippage, fees, funding, stops
    6. calculate metrics              - trades, equity, P&L, drawdown, exposure
    7. write machine-readable result  - BacktestResult, never prose
    8. hand to critic                 - structured evidence only

Step 4 is where look-ahead bias enters if you are careless. Every indicator is computed
on a shifted window and the engine asserts it afterwards (see lookahead.py) rather than
trusting the implementation.

Engine choice (§22): a constrained internal Python engine first, because its execution
semantics are knowable. Vectorised libraries are acceptable for screening; the final
validation path keeps known semantics. LEAN is the escape hatch if order semantics
outgrow this.
"""

from __future__ import annotations


def run(spec: object, manifest: object) -> object:
    """Execute one backtest. Returns a BacktestResult.

    Deterministic: same spec + same manifest => byte-identical metrics.
    """
    raise NotImplementedError("Experiment 003 / Week 7-8")
