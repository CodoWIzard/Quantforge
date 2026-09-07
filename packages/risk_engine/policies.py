"""Hard limits that a strategy cannot raise and an agent cannot override.

§35 risk-control hierarchy, from outermost to innermost:

    strategy rules -> portfolio policy -> pre-trade validation
                   -> execution adapter -> runtime monitor -> emergency control

A StrategySpec may set values *tighter* than these. It may never set them looser.
"""

from __future__ import annotations


class HardLimits:
    """Platform ceiling. Loaded from config, never from a model response."""

    max_risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    max_open_positions: int = 5
    max_orders_per_minute: int = 10
    max_data_staleness_seconds: int = 30
