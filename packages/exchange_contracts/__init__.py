"""Kraken-specific vocabulary, isolated from the rest of the system.

ADR-001 fixes the internship to one exchange, but the point of this package is that
symbols, fee tiers, tick sizes and order semantics live in exactly one place. When a
second venue is eventually added (§53), this is the only package that grows.
"""

from .fees import FeeModel
from .orders import OrderIntent, OrderSide, OrderType
from .symbols import SYMBOLS

__all__ = ["SYMBOLS", "FeeModel", "OrderIntent", "OrderSide", "OrderType"]
