"""Order intent - what the strategy wants - versus the venue request.

An OrderIntent is produced by the signal engine and must survive risk checks before an
adapter is allowed to translate it. Keeping intent and request separate is what makes
"AI never places orders" enforceable rather than aspirational (§11).

Idempotency: every intent carries a client-generated key so a retry after a timeout
cannot create a second position (§35 execution adapter).
"""

from __future__ import annotations

from typing import Literal

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


class OrderIntent:
    idempotency_key: str
    strategy_id: str
    strategy_version: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: float | None
    reduce_only: bool
