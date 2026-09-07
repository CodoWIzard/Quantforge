"""Venue constants are load-bearing - a wrong tick silently fabricates fills.

Offline assertions only. The live-API check is marked so CI never depends on the
network, but a human can run it to confirm the committed numbers still match Kraken.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

from packages.exchange_contracts import symbols as S

CANONICAL = {"BTC-PERP", "ETH-PERP"}


def test_scope_is_btc_and_eth_only():
    """ADR-001 - one exchange, two markets."""
    assert set(S.SYMBOLS) == CANONICAL


def test_every_symbol_has_a_tick_and_a_size_precision():
    """An empty dict here is what the code shipped with - it must never regress."""
    for sym in CANONICAL:
        assert S.TICK_SIZE.get(sym), f"{sym} has no tick size"
        assert S.SIZE_PRECISION.get(sym) is not None, f"{sym} has no size precision"


def test_ticks_are_positive():
    assert all(t > 0 for t in S.TICK_SIZE.values())


def test_min_order_size_derives_from_precision():
    for sym, prec in S.SIZE_PRECISION.items():
        assert S.MIN_ORDER_SIZE[sym] == pytest.approx(10 ** -prec)


def test_provenance_is_recorded():
    """Numbers copied from a venue must say where and when, or they rot unnoticed."""
    assert S.INSTRUMENTS_URL.startswith("https://")
    assert S.INSTRUMENTS_FETCHED


def test_round_to_tick_snaps_to_the_grid():
    assert S.round_to_tick("BTC-PERP", 65432.7) == 65433.0
    assert S.round_to_tick("ETH-PERP", 3421.46) == pytest.approx(3421.5)


def test_round_to_tick_is_idempotent():
    once = S.round_to_tick("BTC-PERP", 101.4)
    assert S.round_to_tick("BTC-PERP", once) == once


@pytest.mark.live
def test_committed_ticks_still_match_kraken():
    """Run manually: pytest -m live. Never in CI - no test may need the network."""
    assert S.INSTRUMENTS_URL.startswith("https://"), "refuse non-https fetch"
    with urllib.request.urlopen(S.INSTRUMENTS_URL, timeout=20) as r:  # noqa: S310
        data = json.load(r)
    live = {i["symbol"].upper(): i for i in data["instruments"]}
    for canonical, venue in S.SYMBOLS.items():
        inst = live[venue.upper()]
        assert float(inst["tickSize"]) == S.TICK_SIZE[canonical], canonical
        assert int(inst["contractValueTradePrecision"]) == S.SIZE_PRECISION[canonical]
