"""Pre-trade validation. Fails CLOSED.

Blueprint §12: *"stale data, invalid rules, failed risk checks or uncertain exchange
state stop new orders."* And §24: *"Any failed check => no new order."*

The checks, from §24 and §35:

- daily loss limit reached
- max open positions / notional exposure
- max order rate
- price freshness (stale feed)
- exchange connection state uncertain
- duplicate order / idempotency key already seen
- quantity within bounds
"""

from __future__ import annotations


class PreTradeResult:
    """Allow/deny plus the reason. The reason is audited (§34), not just logged."""

    allowed: bool
    reason: str | None


class PreTradeCheck:
    """Runs every gate against an order intent.

    Deliberately boring and total: no early return that skips a later check, so the
    audit record shows every gate that was evaluated.
    """

    def evaluate(self, order_intent: object, account_state: object) -> PreTradeResult:
        raise NotImplementedError("Week 13-14: risk + persistence")
