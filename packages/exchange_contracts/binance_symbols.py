"""Symbol mapping between QuantForge canonical names and BINANCE USD-M venue names.

ADR-012: Binance is the market data source. This module is the Binance vocabulary;
`symbols.py` holds the stale Kraken one and is kept deliberately unconverted.

Every number here was read from Binance's own instrument list, never translated from
the Kraken module. That is not pedantry — the ticks differ by a factor of ten:

    canonical   Kraken tick (symbols.py)   Binance tick (here)
    BTC-PERP    1.0                        0.10
    ETH-PERP    0.1                        0.01

Renaming `PF_XBTUSD` to `BTCUSDT` while keeping the tick would have silently priced
every simulated fill on a grid 10x too coarse, and nothing downstream would complain.

Refresh with `scripts/fetch_binance_symbols.py`, which prints a diff and does not
write; a venue changing a tick is a decision for a human, not a script.
"""

from __future__ import annotations

from decimal import Decimal

#: canonical -> venue symbol (USD-M perpetuals).
SYMBOLS: dict[str, str] = {
    "BTC-PERP": "BTCUSDT",
    "ETH-PERP": "ETHUSDT",
}

#: venue -> canonical, for the inbound adapter direction.
CANONICAL: dict[str, str] = {v: k for k, v in SYMBOLS.items()}

#: Minimum price increment (PRICE_FILTER.tickSize). Decimal, not float: 0.01 has no
#: exact binary representation, and a rounding step is exactly where that bites.
TICK_SIZE: dict[str, Decimal] = {
    "BTC-PERP": Decimal("0.10"),
    "ETH-PERP": Decimal("0.01"),
}

#: Minimum order size increment (LOT_SIZE.stepSize).
STEP_SIZE: dict[str, Decimal] = {
    "BTC-PERP": Decimal("0.001"),
    "ETH-PERP": Decimal("0.001"),
}

#: Smallest tradeable size (LOT_SIZE.minQty). Read from the venue, not derived from
#: STEP_SIZE — they coincide today and that is not guaranteed.
MIN_ORDER_SIZE: dict[str, Decimal] = {
    "BTC-PERP": Decimal("0.001"),
    "ETH-PERP": Decimal("0.001"),
}

#: Decimal places the venue accepts on price / quantity.
PRICE_PRECISION: dict[str, int] = {"BTC-PERP": 2, "ETH-PERP": 2}
QTY_PRECISION: dict[str, int] = {"BTC-PERP": 3, "ETH-PERP": 3}

#: Provenance, so a future reader can re-check rather than trust.
INSTRUMENTS_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
INSTRUMENTS_FETCHED = "2026-09-30"
CONTRACT_TYPE = "PERPETUAL"

#: Timeframes StrategySpec permits, mapped to Binance's kline interval strings.
#: Deliberately only these three: the schema allows 1m/5m/15m, so a wider map here
#: would let a caller fetch data no strategy can legally reference.
INTERVALS: dict[str, str] = {"1m": "1m", "5m": "5m", "15m": "15m"}


def venue_symbol(canonical: str) -> str:
    """Canonical -> Binance ticker. Raises on anything unmapped.

    An unknown symbol is an error, never a guess: `AGENTS.md` forbids inventing an
    unspecified parameter, and a silently passed-through ticker would reach the
    venue as a 400 at best and the wrong market at worst.
    """
    try:
        return SYMBOLS[canonical]
    except KeyError:
        raise KeyError(
            f"{canonical!r} is not a QuantForge canonical symbol; "
            f"known: {sorted(SYMBOLS)}"
        ) from None


def venue_interval(timeframe: str) -> str:
    """StrategySpec timeframe -> Binance interval. Raises on unsupported ones."""
    try:
        return INTERVALS[timeframe]
    except KeyError:
        raise KeyError(
            f"{timeframe!r} is not a supported timeframe; known: {sorted(INTERVALS)}"
        ) from None
