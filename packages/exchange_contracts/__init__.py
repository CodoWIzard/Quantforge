"""Kraken vocabulary — STALE as of ADR-012. Isolated from the rest of the system.

ADR-012 moved market data to Binance and paper/demo execution to TradingView.
Kraken is no longer a venue for this project, so every symbol, tick and fee in
this package now describes a market QuantForge does not trade. It is kept rather
than deleted because the numbers were fetched from the live venue and are the
worked example of how a venue package should be built, and because nothing here
is imported by working code yet.

Do NOT adapt it by renaming: `PF_XBTUSD` -> `BTCUSDT` is a one-line edit that
carries Kraken's tick sizes and size precision into a Binance context, and a
wrong tick size silently corrupts every simulated fill. A Binance package is a
NEW package built from Binance's own instrument list, beside this one.

The original point stands and is why this is a package at all: symbols, fee
tiers, tick sizes and order semantics live in exactly one place per venue.
"""

from .fees import FeeModel
from .orders import OrderIntent, OrderSide, OrderType
from .symbols import SYMBOLS

__all__ = ["SYMBOLS", "FeeModel", "OrderIntent", "OrderSide", "OrderType"]
