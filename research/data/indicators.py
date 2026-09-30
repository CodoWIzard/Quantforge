"""Deterministic indicator and statistic tools. Agents call these instead of guessing.

Week 3 board card: *"[Jaedyn] Add basic indicator/stat tools: SMA, returns, volatility,
simple volume comparison"*, and the card's "Done when": *agents can use tool outputs for
real market data checks, indicators, basic statistics and strategy input validation
instead of guessing numbers.*

Every function here is pure: same input, same output, no clock, no network, no model. That
is the whole point — these are the numbers an agent is allowed to cite, and a reviewer can
recompute any of them by hand.

DESIGN RULES, each learned from a way this goes wrong
1. Insufficient data RAISES; it never returns a shorter answer. `sma(prices, 20)` on 19
   bars is not a 19-period average — it is a different statistic wearing the same name.
2. No NaN padding. A NaN that reaches a comparison makes `>` silently False, so a strategy
   "didn't trigger" for a reason nobody can see. Series functions return the aligned tail
   plus the index it starts at.
3. Volatility states its own annualisation. An unlabelled "0.04" is uninterpretable, and
   two of them from different timeframes get compared anyway.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


class InsufficientDataError(ValueError):
    """Fewer bars than the requested window needs.

    Distinct from ValueError so a caller can tell "your window is too long for this data"
    (recoverable: fetch more, or shorten) from "your input is nonsense".
    """


@dataclass(frozen=True)
class Series:
    """A computed series plus WHERE it starts relative to the input.

    `offset` is the index of the first input bar the first value corresponds to. Without
    it, a caller zips a 20-period SMA against the raw prices and silently misaligns every
    comparison by 19 bars — the bug that looks like a profitable strategy.
    """

    values: list[float]
    offset: int
    label: str

    def __len__(self) -> int:
        return len(self.values)

    @property
    def last(self) -> float:
        if not self.values:
            raise InsufficientDataError(f"{self.label} is empty")
        return self.values[-1]


def _check(data: list[float], window: int, name: str) -> None:
    if window <= 0:
        raise ValueError(f"{name}: window must be positive, got {window}")
    if len(data) < window:
        raise InsufficientDataError(
            f"{name}: need at least {window} bars, got {len(data)}"
        )


def sma(data: list[float], window: int) -> Series:
    """Simple moving average. Rolling sum, so cost is O(n) not O(n*window)."""
    _check(data, window, f"sma({window})")
    out: list[float] = []
    total = sum(data[:window])
    out.append(total / window)
    for i in range(window, len(data)):
        total += data[i] - data[i - window]
        out.append(total / window)
    return Series(out, offset=window - 1, label=f"sma({window})")


def simple_returns(prices: list[float]) -> Series:
    """Bar-over-bar simple returns, (p[i] / p[i-1]) - 1.

    Raises on a non-positive price rather than producing a meaningless ratio: a zero or
    negative price in OHLC data is a data defect, and dividing by it would hide it.
    """
    if len(prices) < 2:
        raise InsufficientDataError("simple_returns: need at least 2 prices")
    out: list[float] = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        if prev <= 0:
            raise ValueError(f"simple_returns: non-positive price {prev} at index {i - 1}")
        out.append(prices[i] / prev - 1.0)
    return Series(out, offset=1, label="simple_returns")


def log_returns(prices: list[float]) -> Series:
    """Natural log returns. Preferred for volatility: additive across time."""
    if len(prices) < 2:
        raise InsufficientDataError("log_returns: need at least 2 prices")
    out: list[float] = []
    for i in range(1, len(prices)):
        prev, cur = prices[i - 1], prices[i]
        if prev <= 0 or cur <= 0:
            raise ValueError(f"log_returns: non-positive price at index {i - 1}/{i}")
        out.append(math.log(cur / prev))
    return Series(out, offset=1, label="log_returns")


def stdev(data: list[float], sample: bool = True) -> float:
    """Standard deviation. Sample (n-1) by default — these are always samples.

    The population form understates dispersion on small windows, which flatters exactly
    the risk metrics we most need not flattered.
    """
    n = len(data)
    if n < 2:
        raise InsufficientDataError(f"stdev: need at least 2 values, got {n}")
    mean = sum(data) / n
    denom = n - 1 if sample else n
    return math.sqrt(sum((x - mean) ** 2 for x in data) / denom)


#: Bars per 365-day year, per timeframe. Crypto trades continuously — no 252-day
#: equity convention here, and using one would understate annual vol by ~40%.
BARS_PER_YEAR: dict[str, int] = {
    "1m": 365 * 24 * 60,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
}


@dataclass(frozen=True)
class Volatility:
    """A volatility measurement that carries its own units. Never a bare float."""

    per_bar: float
    annualised: float
    timeframe: str
    bars_used: int
    basis: str = "log returns, sample stdev, 365-day year"

    def __str__(self) -> str:
        return (
            f"{self.annualised:.1%} annualised ({self.per_bar:.4%}/bar, {self.timeframe}, "
            f"n={self.bars_used}, {self.basis})"
        )


def volatility(prices: list[float], timeframe: str) -> Volatility:
    """Realised volatility from log returns, annualised for the given timeframe."""
    if timeframe not in BARS_PER_YEAR:
        raise ValueError(
            f"volatility: unknown timeframe {timeframe!r}; known {sorted(BARS_PER_YEAR)}"
        )
    r = log_returns(prices)
    per_bar = stdev(r.values)
    return Volatility(
        per_bar=per_bar,
        annualised=per_bar * math.sqrt(BARS_PER_YEAR[timeframe]),
        timeframe=timeframe,
        bars_used=len(r),
    )


@dataclass(frozen=True)
class VolumeComparison:
    """Current volume against its own recent average — the card's 'volume comparison'."""

    current: float
    average: float
    ratio: float
    window: int
    threshold: float
    exceeds: bool

    def __str__(self) -> str:
        verdict = "EXCEEDS" if self.exceeds else "below"
        return (
            f"volume {self.current:,.2f} vs sma({self.window}) {self.average:,.2f} "
            f"= {self.ratio:.2f}x, {verdict} {self.threshold}x threshold"
        )


def volume_comparison(
    volumes: list[float], window: int = 20, threshold: float = 1.5
) -> VolumeComparison:
    """Is the latest bar's volume `threshold`x its trailing average?

    Needs window+1 bars, not window: the average must EXCLUDE the bar being judged, or a
    genuine spike inflates the baseline it is measured against and partly hides itself.
    """
    if len(volumes) < window + 1:
        raise InsufficientDataError(
            f"volume_comparison: need {window + 1} bars (window excludes the current "
            f"bar), got {len(volumes)}"
        )
    current = volumes[-1]
    baseline = volumes[-(window + 1):-1]
    average = sum(baseline) / window
    if average <= 0:
        raise ValueError(
            f"volume_comparison: trailing average is {average}; ratio is undefined. "
            "Zero-volume baselines usually mean a data gap, not a quiet market."
        )
    ratio = current / average
    return VolumeComparison(current, average, ratio, window, threshold, ratio > threshold)


def max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough fractional decline. Returns a POSITIVE fraction.

    Sign is a documented choice: 0.23 means "lost 23% from the peak". Half the libraries
    return this negative, so the docstring is load-bearing.
    """
    if len(equity) < 2:
        raise InsufficientDataError("max_drawdown: need at least 2 points")
    peak, worst = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst
