"""Scanner tests. The scanner is dormant; these prove the design, not a live edge."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.scanner import scanner as sc
from services.scanner.halt import evaluate
from services.scanner.registry import ModelResult, ScanModel, select_best
from services.scanner.types import Candle
from services.scanner.windows import WINDOWS, current_window, next_window


def candle(close=100.0, *, open_=100.0, high=None, low=None, volume=10.0, t=0, closed=True):
    high = max(open_, close) if high is None else high
    low = min(open_, close) if low is None else low
    return Candle(t, open_, high, low, close, volume, closed)


def calm(n=60):
    return [candle(t=i * 3_600_000) for i in range(n)]


def model(key, result, threshold=55, rank=100, directional=None):
    return ScanModel(
        key=key,
        name=key,
        threshold=threshold,
        score_fn=lambda ctx, r=result: r,
        evidence_ref="test-fixture",
        directional_threshold=directional or {},
        rank=rank,
    )


def ctx(candles=None, *, has_position=False):
    candles = candles or calm()
    return sc.ScanContext(
        symbol="BTC-PERP",
        now=datetime(2026, 9, 11, 8, 0, tzinfo=UTC),
        price=100.0,
        candles_1h=candles,
        candles_4h=candles,
        candles_1d=candles,
        window=WINDOWS[1],
        has_open_position=has_position,
    )


# --- the dormancy guarantee -------------------------------------------------

def test_scanner_is_dormant():
    """ENABLED must stay False until a validated model and a data tool exist.

    This test is the tripwire for the instruction 'copy the design but do not
    make it active'. Flipping ENABLED without meeting the preconditions in
    scanner.py fails here.
    """
    assert sc.ENABLED is False


def test_run_scan_refuses_while_dormant():
    with pytest.raises(sc.ScannerDisabledError):
        sc.run_scan(ctx())


# --- registry ---------------------------------------------------------------

def test_model_without_evidence_cannot_register():
    """A scorer with no backtest reference must not become a live model."""
    from services.scanner.registry import register_model

    bad = ScanModel("X", "X", 55, lambda ctx: ModelResult(0), evidence_ref="  ")
    with pytest.raises(ValueError, match="evidence_ref"):
        register_model(bad)


def test_no_models_is_not_the_same_as_no_setups():
    """An empty registry must be reported explicitly, not as a quiet scan."""
    report = sc._scan(ctx(), models=[])
    assert report.no_models is True
    assert report.triggered is False


def test_blocked_model_keeps_score_none():
    """score None (gated) must not collapse into score 0 (ran, found nothing)."""
    r = ModelResult(None, blocked_by="ADX 38 too high")
    report = sc._scan(ctx(), models=[model("G", r)])
    assert report.scores[0][1].score is None


def test_rejects_impossible_direction():
    with pytest.raises(ValueError, match="direction"):
        ModelResult(60, "SIDEWAYS")


# --- selection rules --------------------------------------------------------

def test_highest_score_wins():
    a = (model("A", ModelResult(60, "LONG")), ModelResult(60, "LONG"))
    b = (model("B", ModelResult(80, "LONG")), ModelResult(80, "LONG"))
    assert select_best([a, b])[0].key == "B"


def test_tie_within_band_falls_back_to_rank():
    """Within 3 points the better-evidenced model wins, not the higher score."""
    a = (model("A", ModelResult(60, "LONG"), rank=1), ModelResult(60, "LONG"))
    b = (model("B", ModelResult(62, "LONG"), rank=9), ModelResult(62, "LONG"))
    assert select_best([a, b])[0].key == "A"


def test_long_and_short_both_qualifying_stands_aside():
    """The conflict rule: never resolve a two-sided signal by picking one."""
    a = (model("A", ModelResult(70, "LONG")), ModelResult(70, "LONG"))
    b = (model("B", ModelResult(90, "SHORT")), ModelResult(90, "SHORT"))
    assert select_best([a, b]) is None

    report = sc._scan(ctx(), models=[a[0], b[0]])
    assert report.conflict is True
    assert report.selected is None


def test_directional_threshold_blocks_the_weaker_side():
    """Model T shorts needed 80 while longs needed 70; a flat bar let weak shorts through."""
    m = model("T", ModelResult(75, "SHORT"), threshold=70, directional={"SHORT": 80})
    assert select_best([(m, ModelResult(75, "SHORT"))]) is None
    assert select_best([(m, ModelResult(75, "LONG"))]) is not None


def test_open_position_blocks_entry_but_still_scores():
    report = sc._scan(ctx(has_position=True), models=[model("G", ModelResult(90, "LONG"))])
    assert report.position_open is True
    assert report.selected is None
    assert report.scores, "shadow scan must still publish scores"


# --- halt shield ------------------------------------------------------------

def test_short_history_halts_rather_than_passing():
    """A data outage must not look like a calm market."""
    assert evaluate(calm(5)).halted is True


def test_flash_move_halts():
    c = calm()
    c[-1] = candle(open_=100.0, close=106.0, t=99)
    d = evaluate(c)
    assert d.halted and d.severity == "CRITICAL"


def test_volume_spike_halts():
    c = calm()
    c[-1] = candle(volume=500.0, t=99)
    assert evaluate(c).halted is True


def test_consecutive_extremes_halt():
    c = calm()
    c[-2] = candle(open_=100.0, close=103.5, t=98)
    c[-1] = candle(open_=100.0, close=103.5, t=99)
    assert evaluate(c).halted is True


def test_calm_market_does_not_halt():
    assert evaluate(calm()).halted is False


def test_halt_precedes_scoring():
    """A halted market must never reach a model."""
    def explode(ctx):
        raise AssertionError("model scored during a halt")

    m = ScanModel("X", "X", 55, explode, evidence_ref="test")
    report = sc._scan(ctx(calm(5)), models=[m])
    assert report.halted is True


# --- candle integrity -------------------------------------------------------

def test_candle_rejects_close_outside_range():
    with pytest.raises(ValueError, match="close"):
        Candle(0, 100.0, 101.0, 99.0, 105.0, 1.0, True)


def test_candle_rejects_inverted_high_low():
    with pytest.raises(ValueError, match="high"):
        Candle(0, 100.0, 90.0, 110.0, 100.0, 1.0, True)


# --- windows ----------------------------------------------------------------

def test_window_matches_minute_not_just_hour():
    """13:00 is not NY_AM; NY_AM opens 13:30."""
    assert current_window(datetime(2026, 9, 11, 13, 0, tzinfo=UTC)) is None
    assert current_window(datetime(2026, 9, 11, 13, 30, tzinfo=UTC)).name == "NY_AM"


def test_next_window_wraps_past_midnight():
    w, delta = next_window(datetime(2026, 9, 11, 23, 0, tzinfo=UTC))
    assert w.name == "Asian"
    assert delta.total_seconds() == 2 * 3600
