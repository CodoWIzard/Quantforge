"""Market-wide trading halt (the "black swan shield").

Ported from the original scanner. This is the one piece of that design that is
model-independent: it asks whether the market itself is in a state where any
signal should be distrusted, before a single model scores.

Kept because it is pure arithmetic on closed candles - no venue call, no model,
no LLM - and because it fails CLOSED. An unreadable or too-short candle series
halts scanning rather than passing silently.

Thresholds are the original's, carried over as-is. They have not been re-derived
against a QuantForge RunManifest, so HALT_THRESHOLDS_EVIDENCE says exactly that:
a future reader must not mistake inherited constants for validated ones.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .types import Candle

HALT_THRESHOLDS_EVIDENCE = (
    "Inherited from the BTC kill-zone scanner (live since 2026-05). NOT yet "
    "re-validated against a QuantForge RunManifest. Treat as provisional."
)

FLASH_MOVE_PCT = 5.0
CONSECUTIVE_MOVE_PCT = 3.0
VOLUME_SPIKE_RATIO = 3.0
ATR_SPIKE_RATIO = 2.5
MIN_CANDLES = 25
ATR_PERIOD = 14


@dataclass(frozen=True)
class HaltDecision:
    halted: bool
    reason: str = ""
    severity: str = ""  # "CRITICAL" | "HIGH" | ""


def _atr(candles: Sequence[Candle], period: int = ATR_PERIOD) -> tuple[float, float]:
    """Current ATR and the preceding baseline ATR."""
    trs: list[float] = []
    for i in range(1, len(candles)):
        h, low, prev_close = candles[i].high, candles[i].low, candles[i - 1].close
        trs.append(max(h - low, abs(h - prev_close), abs(low - prev_close)))
    if not trs:
        return 0.0, 0.0
    if len(trs) < period:
        return trs[-1], sum(trs) / len(trs)
    current = sum(trs[-period:]) / period
    baseline = (
        sum(trs[-period * 2 : -period]) / period if len(trs) >= period * 2 else current
    )
    return current, baseline


def evaluate(candles_1h: Sequence[Candle]) -> HaltDecision:
    """Decide whether to halt all scanning.

    Fails closed on insufficient data. The original returned "no halt" when it
    had fewer than 25 candles, which means a data outage looked exactly like a
    calm market - the most dangerous moment to be trading blind.
    """
    if len(candles_1h) < MIN_CANDLES:
        return HaltDecision(
            True,
            f"insufficient history: {len(candles_1h)} candles, need {MIN_CANDLES}",
            "CRITICAL",
        )

    window = list(candles_1h[-60:])
    last, prev = window[-1], window[-2]

    last_move = abs(last.close - last.open) / last.open * 100
    if last_move >= FLASH_MOVE_PCT:
        return HaltDecision(True, f"flash move {last_move:.1f}% on last 1H candle", "CRITICAL")

    vols = [c.volume for c in window[:-1]]
    avg_vol = sum(vols) / len(vols) if vols else 0.0
    if avg_vol > 0 and last.volume / avg_vol >= VOLUME_SPIKE_RATIO:
        ratio = last.volume / avg_vol
        return HaltDecision(True, f"volume spike {ratio:.1f}x above average", "HIGH")

    current_atr, baseline_atr = _atr(window)
    if baseline_atr > 0 and current_atr / baseline_atr >= ATR_SPIKE_RATIO:
        ratio = current_atr / baseline_atr
        return HaltDecision(True, f"ATR spike {ratio:.1f}x above baseline", "HIGH")

    prev_move = abs(prev.close - prev.open) / prev.open * 100
    if last_move >= CONSECUTIVE_MOVE_PCT and prev_move >= CONSECUTIVE_MOVE_PCT:
        return HaltDecision(
            True, f"consecutive extreme candles {prev_move:.1f}% + {last_move:.1f}%", "HIGH"
        )

    return HaltDecision(False)
