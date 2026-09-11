"""Symbol mapping between QuantForge canonical names and KRAKEN venue names.

STALE (ADR-012): Kraken is no longer a venue for this project — data is Binance,
paper execution is TradingView. Every number below is a correct reading of a
market QuantForge does not use. Do not rename the tickers to Binance ones and
keep the ticks; build a separate Binance module from Binance's instrument list.

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

#: Minimum price increment, canonical symbol -> tick.
#: Fetched 2026-09-07 from https://futures.kraken.com/derivatives/api/v3/instruments
#: (public, no auth). A WRONG tick size silently corrupts every simulated fill, so these
#: are copied from the venue rather than assumed - and re-verified by a test, not trusted.
TICK_SIZE: dict[str, float] = {
    "BTC-PERP": 1.0,
    "ETH-PERP": 0.1,
}

#: Decimal places allowed on order size (Kraken: contractValueTradePrecision).
SIZE_PRECISION: dict[str, int] = {
    "BTC-PERP": 4,
    "ETH-PERP": 3,
}

#: Smallest tradeable size, derived from SIZE_PRECISION.
MIN_ORDER_SIZE: dict[str, float] = {
    sym: 10 ** -prec for sym, prec in SIZE_PRECISION.items()
}

#: Where the numbers above came from, so a future reader can re-check them.
INSTRUMENTS_URL = "https://futures.kraken.com/derivatives/api/v3/instruments"
INSTRUMENTS_FETCHED = "2026-09-07"


def round_to_tick(symbol: str, price: float) -> float:
    """Snap a price to the venue's tick grid.

    An unrounded price is rejected by the exchange, so a backtest that fills at an
    impossible price is measuring a trade that could never have happened.
    """
    tick = TICK_SIZE[symbol]
    return round(round(price / tick) * tick, 10)
