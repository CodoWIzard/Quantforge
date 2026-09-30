"""Tests for the Week 3 data + tool layer.

No network, no credentials, and no dependence on the lake being populated: the data tests
skip cleanly when it is empty so CI stays green on a fresh clone, while still being real
tests on a machine that has run the downloader.

The indicator tests use hand-computable fixtures on purpose. An indicator checked only
against another library's output tests agreement, not correctness; [1,2,3,4,5] has a mean
of 3 whether or not anyone's code works.
"""

from __future__ import annotations

import datetime as dt
import math

import pytest

from packages.exchange_contracts import binance_symbols as bx
from packages.exchange_contracts import symbols as kraken
from research.data.candles import (
    BAR_SECONDS,
    Candle,
    DataUnavailableError,
    UnsupportedTimeframeError,
    available,
    read_candles,
    validate,
)
from research.data.indicators import (
    InsufficientDataError,
    log_returns,
    max_drawdown,
    simple_returns,
    sma,
    stdev,
    volatility,
    volume_comparison,
)
from research.data.tools import TOOL_SCHEMAS, TOOLS, call

UTC = dt.UTC


def _c(minute: int, o=100.0, h=101.0, low=99.0, c=100.5, v=10.0, tf_s=900) -> Candle:
    return Candle(
        open_time=dt.datetime(2026, 6, 1, tzinfo=UTC) + dt.timedelta(seconds=minute * tf_s),
        open=o, high=h, low=low, close=c, volume=v, trades=5,
    )


# --- the venue vocabulary ----------------------------------------------------

def test_binance_ticks_were_not_inherited_from_kraken():
    """The whole reason binance_symbols.py is a separate module.

    Kraken's BTC tick is 1.0, Binance's is 0.10 — a 10x difference. If these ever match,
    somebody has hand-translated the stale module instead of reading the venue, and every
    simulated fill lands on a price grid that does not exist.
    """
    assert float(bx.TICK_SIZE["BTC-PERP"]) == 0.10
    assert float(bx.TICK_SIZE["ETH-PERP"]) == 0.01
    assert float(bx.TICK_SIZE["BTC-PERP"]) != kraken.TICK_SIZE["BTC-PERP"]
    assert float(bx.TICK_SIZE["ETH-PERP"]) != kraken.TICK_SIZE["ETH-PERP"]


def test_binance_ticks_are_decimal_not_float():
    """0.01 has no exact binary representation; a rounding step is where that bites."""
    from decimal import Decimal
    for v in list(bx.TICK_SIZE.values()) + list(bx.STEP_SIZE.values()):
        assert isinstance(v, Decimal)


def test_intervals_cover_exactly_the_timeframes_strategyspec_permits():
    """A 1h entry here would let a caller fetch data no strategy may legally reference."""
    assert set(bx.INTERVALS) == {"1m", "5m", "15m"}
    assert set(BAR_SECONDS) == set(bx.INTERVALS)


def test_unknown_symbol_and_timeframe_raise_rather_than_pass_through():
    with pytest.raises(KeyError):
        bx.venue_symbol("DOGE-PERP")
    with pytest.raises(KeyError):
        bx.venue_interval("1h")


def test_canonical_is_the_inverse_of_symbols():
    for canon, venue in bx.SYMBOLS.items():
        assert bx.CANONICAL[venue] == canon


# --- indicators, on hand-computable fixtures --------------------------------

def test_sma_matches_arithmetic_done_by_hand():
    s = sma([1.0, 2.0, 3.0, 4.0, 5.0], 3)
    assert s.values == [2.0, 3.0, 4.0]
    assert s.offset == 2  # first value describes input index 2
    assert s.last == 4.0


def test_sma_offset_is_what_stops_a_silent_misalignment():
    """A 20-period SMA zipped against raw prices without the offset misaligns by 19 bars
    — the bug that looks like a profitable strategy."""
    prices = list(range(100))
    s = sma([float(p) for p in prices], 20)
    assert s.offset == 19
    assert len(s) == len(prices) - 19


def test_sma_raises_rather_than_returning_a_shorter_window():
    """sma(20) on 19 bars is a different statistic wearing the same name."""
    with pytest.raises(InsufficientDataError):
        sma([1.0] * 19, 20)


def test_sma_rejects_a_non_positive_window():
    with pytest.raises(ValueError):
        sma([1.0, 2.0], 0)


def test_simple_and_log_returns_agree_on_small_moves_and_differ_on_large():
    assert simple_returns([100.0, 101.0]).last == pytest.approx(0.01)
    assert log_returns([100.0, 101.0]).last == pytest.approx(math.log(1.01))
    assert log_returns([100.0, 200.0]).last == pytest.approx(math.log(2))


def test_returns_reject_non_positive_prices_instead_of_dividing():
    """A zero price in OHLC is a data defect; a ratio would hide it."""
    with pytest.raises(ValueError):
        simple_returns([0.0, 100.0])
    with pytest.raises(ValueError):
        log_returns([100.0, 0.0])


def test_stdev_is_the_sample_form_by_default():
    """Population stdev understates dispersion, flattering exactly the risk metrics we
    most need un-flattered."""
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    assert stdev(data, sample=False) == pytest.approx(2.0)
    assert stdev(data, sample=True) == pytest.approx(2.13809, abs=1e-5)


def test_volatility_carries_its_units_and_uses_a_365_day_year():
    """An unlabelled 0.04 is uninterpretable, and gets compared across timeframes anyway."""
    prices = [100.0 * (1.001 ** i) for i in range(200)]
    v = volatility(prices, "15m")
    assert v.timeframe == "15m"
    assert v.bars_used == 199
    assert "365-day" in v.basis
    assert "annualised" in str(v)


def test_volatility_scales_with_the_square_root_of_bars_per_year():
    prices = [100.0, 101.0, 100.5, 102.0, 101.0, 103.0, 102.5, 104.0]
    v15, v1 = volatility(prices, "15m"), volatility(prices, "1m")
    assert v15.per_bar == pytest.approx(v1.per_bar)  # same data, same per-bar
    ratio = math.sqrt(bx_bars("1m") / bx_bars("15m"))
    assert v1.annualised / v15.annualised == pytest.approx(ratio)


def bx_bars(tf: str) -> int:
    from research.data.indicators import BARS_PER_YEAR
    return BARS_PER_YEAR[tf]


def test_volatility_rejects_an_unknown_timeframe():
    with pytest.raises(ValueError):
        volatility([100.0, 101.0, 102.0], "1h")


def test_volume_comparison_excludes_the_bar_it_judges():
    """Including the current bar in its own baseline lets a spike inflate the average it
    is measured against, partly hiding itself."""
    vols = [10.0] * 20 + [30.0]
    vc = volume_comparison(vols, window=20, threshold=1.5)
    assert vc.average == 10.0  # not 10.95
    assert vc.ratio == 3.0
    assert vc.exceeds


def test_volume_comparison_needs_window_plus_one_bars():
    with pytest.raises(InsufficientDataError):
        volume_comparison([10.0] * 20, window=20)


def test_volume_comparison_refuses_a_zero_baseline():
    """A zero-volume baseline usually means a data gap, not a quiet market."""
    with pytest.raises(ValueError):
        volume_comparison([0.0] * 20 + [5.0], window=20)


def test_max_drawdown_is_positive_and_hand_checkable():
    assert max_drawdown([100.0, 120.0, 60.0, 90.0]) == pytest.approx(0.5)
    assert max_drawdown([100.0, 110.0, 120.0]) == 0.0


# --- validation reports, never repairs --------------------------------------

def test_validate_finds_a_gap_and_counts_the_missing_bars():
    candles = [_c(0), _c(1), _c(4)]  # bars 2 and 3 absent
    rep = validate(candles, "BTC-PERP", "15m")
    assert len(rep.gaps) == 1
    assert rep.missing_bars == 2
    assert not rep.clean


def test_validate_returns_the_same_candles_it_was_given():
    """The load-bearing property: validation must not repair. A forward-filled bar is a
    price that never traded, inherited by every metric with no trace."""
    candles = [_c(0), _c(1), _c(9)]
    before = list(candles)
    validate(candles, "BTC-PERP", "15m")
    assert candles == before
    assert len(candles) == 3  # no bar was synthesised to close the gap


def test_validate_finds_duplicate_and_out_of_order_timestamps():
    dup = validate([_c(0), _c(1), _c(1)], "BTC-PERP", "15m")
    assert len(dup.duplicates) == 1
    back = validate([_c(0), _c(5), _c(2)], "BTC-PERP", "15m")
    assert back.out_of_order or back.gaps


def test_validate_catches_impossible_ohlc_relationships():
    """A high below the close will not announce itself; it just makes one indicator
    slightly wrong forever."""
    bad_hl = validate([_c(0, h=99.0, low=101.0)], "BTC-PERP", "15m")
    assert bad_hl.ohlc_violations
    close_above = validate([_c(0, o=100.0, h=101.0, low=99.0, c=105.0)], "BTC-PERP", "15m")
    assert close_above.ohlc_violations


def test_validate_catches_non_positive_prices():
    rep = validate([_c(0, o=0.0, h=101.0, low=0.0, c=100.0)], "BTC-PERP", "15m")
    assert rep.non_positive


def test_a_clean_series_reports_clean():
    rep = validate([_c(i) for i in range(10)], "BTC-PERP", "15m")
    assert rep.clean
    assert rep.missing_bars == 0
    assert "CLEAN" in rep.summary()


def test_empty_series_summary_says_empty_rather_than_clean():
    """Zero defects over zero bars is not a clean market."""
    rep = validate([], "BTC-PERP", "15m")
    assert rep.bars == 0
    assert "EMPTY" in rep.summary()


# --- failure behaviour: the card's explicit Verify item ---------------------

def test_read_candles_rejects_an_unsupported_timeframe_before_touching_disk():
    with pytest.raises(UnsupportedTimeframeError):
        read_candles("BTC-PERP", "1h")


def test_missing_data_raises_rather_than_returning_an_empty_list():
    """[] would read as 'a market with no activity', and statistics over nothing get
    reported as if measured."""
    with pytest.raises(DataUnavailableError):
        _force_missing()


def _force_missing():
    from research.data import candles as mod
    orig = mod.lake_path
    try:
        mod.lake_path = lambda s, t: mod.LAKE / "symbol=NOPE" / "timeframe=15m" / "x.parquet"
        return mod.read_candles("BTC-PERP", "15m")
    finally:
        mod.lake_path = orig


def test_wrong_symbol_is_refused_with_the_valid_set_named():
    """A bare 'invalid symbol' teaches a model nothing and it retries with another guess."""
    r = call("describe_market", symbol="DOGE-PERP", timeframe="15m")
    assert not r.ok
    assert r.error_type == "KeyError"
    assert "BTC-PERP" in (r.error or "")


def test_a_venue_ticker_is_refused_like_any_other_unknown_symbol():
    """Strategies are written against canonical names; BTCUSDT must not leak inward."""
    r = call("describe_market", symbol="BTCUSDT", timeframe="15m")
    assert not r.ok


def test_unsupported_timeframe_is_refused_with_its_own_error_type():
    """Pinning the TYPE, not just ok=False: two bugs sharing one exception let a check
    pass for the wrong reason (the F-002 lesson)."""
    r = call("describe_market", symbol="BTC-PERP", timeframe="1h")
    assert not r.ok
    assert r.error_type == "UnsupportedTimeframeError"


def test_unknown_tool_is_refused_and_lists_the_real_surface():
    r = call("no_such_tool", symbol="BTC-PERP", timeframe="15m")
    assert not r.ok
    assert r.error_type == "UnknownToolError"
    for name in TOOLS:
        assert name in (r.error or "")


def test_a_failed_result_carries_no_value():
    """A partially-filled result reads as success to a skimming model and human."""
    r = call("describe_market", symbol="DOGE-PERP", timeframe="15m")
    assert r.value is None
    assert r.error and r.error_type


def test_a_failed_results_citation_says_it_failed():
    r = call("describe_market", symbol="DOGE-PERP", timeframe="15m")
    assert "FAILED" in r.citation()


# --- the tool schema surface ------------------------------------------------

def test_every_tool_has_a_schema_and_every_schema_has_a_tool():
    assert set(TOOLS) == set(TOOL_SCHEMAS)


def test_schemas_forbid_extra_properties_and_enumerate_symbols():
    """additionalProperties:false is what stops an agent passing an unmodelled argument
    and believing it was honoured."""
    for name, s in TOOL_SCHEMAS.items():
        p = s["parameters"]
        assert p["additionalProperties"] is False, name
        assert set(p["properties"]["symbol"]["enum"]) == set(bx.SYMBOLS), name
        assert set(p["properties"]["timeframe"]["enum"]) == set(bx.INTERVALS), name
        assert "symbol" in p["required"] and "timeframe" in p["required"], name
        assert s["description"], name


# --- against the real lake, skipped when it is empty -----------------------

@pytest.mark.skipif(not available(), reason="lake is empty; run research.data.binance_download")
def test_the_real_sample_is_gap_free_and_matches_its_provenance_note():
    for sym, tf in available():
        rep = validate(read_candles(sym, tf), sym, tf)
        assert rep.clean, rep.summary()


@pytest.mark.skipif(not available(), reason="lake is empty")
def test_bar_counts_are_arithmetically_right_for_three_whole_months():
    """June 30d + July 31d + August 31d = 92 days. 15m => 92*96 = 8832."""
    expected = {"15m": 92 * 96, "5m": 92 * 288, "1m": 92 * 1440}
    for sym, tf in available():
        got = len(read_candles(sym, tf))
        assert got == expected[tf], f"{sym} {tf}: {got} != {expected[tf]}"


@pytest.mark.skipif(not available(), reason="lake is empty")
def test_tools_are_deterministic_across_two_identical_calls():
    """A tool reading a clock or iterating a set would drift, invisibly in one run."""
    for name, kw in [
        ("describe_market", {"symbol": "BTC-PERP", "timeframe": "15m"}),
        ("moving_average", {"symbol": "BTC-PERP", "timeframe": "15m", "window": 20}),
        ("realised_volatility", {"symbol": "BTC-PERP", "timeframe": "15m", "bars": 500}),
        ("volume_spike", {"symbol": "BTC-PERP", "timeframe": "15m"}),
    ]:
        assert call(name, **kw).value == call(name, **kw).value, name


@pytest.mark.skipif(not available(), reason="lake is empty")
def test_every_successful_result_carries_a_citable_window():
    """This is the Week 4 groundedness evidence: a quoted number must be recomputable."""
    r = call("realised_volatility", symbol="BTC-PERP", timeframe="15m", bars=500)
    assert r.ok
    for key in ("bars", "first", "last", "source"):
        assert key in r.provenance
    assert "realised_volatility" in r.citation() and "bars" in r.citation()
