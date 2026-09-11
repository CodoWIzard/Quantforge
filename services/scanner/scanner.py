"""The scan cycle. DORMANT - ENABLED is False.

Ported structure from the BTC kill-zone scanner:

    halt check -> score every model -> publish the full scoreboard
    -> select at most one trade -> (execution: refused here)

What is deliberately NOT ported:

* Execution. The original double-forks tv_paper_trade.py. paper_deploy() does
  not exist in this repository yet, so run_scan() returns a report and the
  caller has nothing to execute with. No stub that pretends.
* Position sizing, fees, leverage. The original carries risk 10%, Bitvavo
  0.25% taker, 10x cap. Those are venue- and account-specific; the data source
  here is under review (Binance) and the execution venue is undecided. Inventing
  them would put fabricated costs into a P&L line.
* The balance default (146376.0). A hardcoded paper balance silently sizes every
  trade against a number nobody checked.

What IS ported, because it is the actual design:

* One position at a time, enforced before scoring finishes.
* Publish EVERY scan, trigger or not, with per-model scores and block reasons -
  a scanner that only speaks when it fires is indistinguishable from a dead one.
* Per-model and per-direction thresholds.
* Conflict rule: LONG and SHORT both qualifying means stand aside.
* Fail-closed halt shield ahead of all scoring.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from . import halt, windows
from .registry import ModelResult, ScanModel, registered_models, select_best
from .types import Candle

#: Master switch. The scanner does not run while this is False.
#:
#: Preconditions for flipping it, all currently unmet:
#:   1. At least one model registered with a QuantForge RunManifest behind it.
#:   2. get_market_data() implemented and pinning its source in the manifest.
#:   3. paper_deploy() implemented, or the scanner declared publish-only.
#:   4. Data source decided (Binance vs Kraken) and fees/ticks re-fetched.
ENABLED = False


class ScannerDisabledError(RuntimeError):
    """Raised when the scanner is invoked while dormant."""


@dataclass(frozen=True)
class ScanContext:
    """Everything a model is allowed to look at.

    One object instead of the original's six different call signatures. A model
    that wants the scan hour reads context.now, not a positional argument that
    only some models accept.
    """

    symbol: str
    now: datetime
    price: float
    candles_1h: Sequence[Candle]
    candles_4h: Sequence[Candle]
    candles_1d: Sequence[Candle]
    window: windows.Window | None
    has_open_position: bool


@dataclass(frozen=True)
class ScanReport:
    """The result of one scan. Publishable as-is; contains no interpretation."""

    symbol: str
    scanned_at: datetime
    window_name: str
    price: float
    halted: bool = False
    halt_reason: str = ""
    halt_severity: str = ""
    position_open: bool = False
    conflict: bool = False
    no_models: bool = False
    scores: list[tuple[str, ModelResult, int]] = field(default_factory=list)
    selected: tuple[str, ModelResult] | None = None

    @property
    def triggered(self) -> bool:
        return self.selected is not None


def run_scan(ctx: ScanContext, *, models: Sequence[ScanModel] | None = None) -> ScanReport:
    """Score every registered model against one bar.

    Raises ScannerDisabledError while ENABLED is False. Callers must not catch
    that and continue - it means the scanner is not ready, not that this scan
    failed.
    """
    if not ENABLED:
        raise ScannerDisabledError(
            "scanner is dormant: no validated model, no market-data tool, and "
            "no paper execution path. See services/scanner/__init__.py."
        )
    return _scan(ctx, models=models)


def _scan(ctx: ScanContext, *, models: Sequence[ScanModel] | None = None) -> ScanReport:
    """The scan cycle itself, callable in tests without flipping ENABLED."""
    active = list(models) if models is not None else registered_models()
    window_name = ctx.window.name if ctx.window else "off-window"
    base = {
        "symbol": ctx.symbol,
        "scanned_at": ctx.now.astimezone(UTC),
        "window_name": window_name,
        "price": ctx.price,
    }

    decision = halt.evaluate(ctx.candles_1h)
    if decision.halted:
        return ScanReport(
            **base,
            halted=True,
            halt_reason=decision.reason,
            halt_severity=decision.severity,
        )

    if not active:
        return ScanReport(**base, no_models=True)

    results = [(m, m.score_fn(ctx)) for m in active]
    scores = [(m.key, r, m.threshold_for(r.direction)) for m, r in results]
    scores.sort(key=lambda row: (row[1].score is None, -(row[1].score or 0)))

    if ctx.has_open_position:
        return ScanReport(**base, position_open=True, scores=scores)

    qualified = [
        (m, r)
        for m, r in results
        if r.score is not None and r.direction and r.score >= m.threshold_for(r.direction)
    ]
    if len({r.direction for _, r in qualified}) > 1:
        return ScanReport(**base, conflict=True, scores=scores)

    best = select_best(results)
    return ScanReport(
        **base,
        scores=scores,
        selected=(best[0].key, best[1]) if best else None,
    )
