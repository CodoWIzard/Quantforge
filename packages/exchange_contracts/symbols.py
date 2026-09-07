"""Symbol mapping between QuantForge canonical names and Kraken venue names.

Canonical names appear in StrategySpec and MarketEvent. Venue names appear only at the
adapter boundary, so a strategy is never written against an exchange-specific ticker.
"""

from __future__ import annotations

#: canonical -> venue symbol. Verify against the live Kraken Futures instrument list
#: before first use; this mapping is from the blueprint's scope decision, not scraped.
SYMBOLS: dict[str, str] = {
    "BTC-PERP": "PF_XBTUSD",
    "ETH-PERP": "PF_ETHUSD",
}

TICK_SIZE: dict[str, float] = {}   # TODO: populate from the instruments endpoint
MIN_ORDER_SIZE: dict[str, float] = {}
