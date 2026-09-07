"""Fee and funding model.

§23 transaction-cost stress asks: *does the edge survive realistic fees, spread,
slippage and funding?* Fees are therefore a first-class input recorded in the
RunManifest, not a constant buried in the backtester.

Rates must be sourced from the venue's published schedule and dated. Do not hardcode a
remembered number - a wrong fee assumption silently manufactures an edge.
"""

from __future__ import annotations


class FeeModel:
    """Maker/taker in basis points plus periodic funding."""

    maker_bps: float
    taker_bps: float
    funding_applied: bool

    def round_trip_cost_pct(self, entry_taker: bool, exit_taker: bool) -> float:
        raise NotImplementedError("Week 7-8: backtest engine")
