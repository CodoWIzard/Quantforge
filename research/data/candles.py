"""Read candles from the Parquet lake and validate their timestamps. No repair, ever.

Week 3 board card: *"[Jayden] Build/load a Python tool for reading candles and validating
timestamps/gaps"*.

This is a deterministic tool, not an agent: it returns numbers and findings, and the agent
cites them. Nothing here calls a model, and nothing here guesses.

WHY VALIDATION AND REPAIR ARE SEPARATE, AND WHY REPAIR IS ABSENT
A reader that silently forward-fills a missing bar hands the backtester a price that never
traded, and every metric computed downstream inherits that fiction with no trace. ADR-004's
`gap_policy` explicitly excludes interpolation. So `validate()` REPORTS:

    GapReport(gaps=[...], duplicates=[...], out_of_order=[...], ohlc_violations=[...])

and the caller decides. A strategy may legitimately tolerate a 2-bar exchange outage; none
may tolerate one being invented for it.
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from packages.exchange_contracts.binance_symbols import INTERVALS  # noqa: E402

LAKE = REPO / "data" / "lake"

#: Bar duration per timeframe. The gap check needs the EXPECTED spacing; deriving it from
#: the data's own modal difference would make a uniformly broken file look perfect.
BAR_SECONDS: dict[str, int] = {"1m": 60, "5m": 300, "15m": 900}


class DataUnavailableError(FileNotFoundError):
    """The requested symbol/timeframe is not in the lake.

    A distinct type because "no data" must never be answerable with an empty list: a
    caller that treats [] as "a market with no activity" computes statistics over nothing
    and reports them as if measured. This is the card's *"failure behavior for missing
    data"* requirement.
    """


class UnsupportedTimeframeError(ValueError):
    """The timeframe is not one StrategySpec permits (1m/5m/15m)."""


@dataclass(frozen=True)
class Candle:
    open_time: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int


@dataclass
class GapReport:
    """Findings about a candle series. `clean` is a derived convenience, not a verdict."""

    symbol: str
    timeframe: str
    bars: int
    first: dt.datetime | None
    last: dt.datetime | None
    gaps: list[tuple[dt.datetime, dt.datetime, int]] = field(default_factory=list)
    duplicates: list[dt.datetime] = field(default_factory=list)
    out_of_order: list[dt.datetime] = field(default_factory=list)
    ohlc_violations: list[tuple[dt.datetime, str]] = field(default_factory=list)
    non_positive: list[tuple[dt.datetime, str]] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (
            self.gaps or self.duplicates or self.out_of_order
            or self.ohlc_violations or self.non_positive
        )

    @property
    def missing_bars(self) -> int:
        return sum(n for _, _, n in self.gaps)

    def summary(self) -> str:
        if self.bars == 0:
            return f"{self.symbol} {self.timeframe}: EMPTY"
        head = (
            f"{self.symbol} {self.timeframe}: {self.bars:,} bars "
            f"{self.first:%Y-%m-%d %H:%M} -> {self.last:%Y-%m-%d %H:%M} UTC"
        )
        if self.clean:
            return head + " | CLEAN"
        parts = []
        if self.gaps:
            parts.append(f"{len(self.gaps)} gaps ({self.missing_bars:,} bars missing)")
        if self.duplicates:
            parts.append(f"{len(self.duplicates)} duplicate timestamps")
        if self.out_of_order:
            parts.append(f"{len(self.out_of_order)} out of order")
        if self.ohlc_violations:
            parts.append(f"{len(self.ohlc_violations)} OHLC violations")
        if self.non_positive:
            parts.append(f"{len(self.non_positive)} non-positive values")
        return head + " | " + "; ".join(parts)


def lake_path(symbol: str, timeframe: str) -> Path:
    return LAKE / f"symbol={symbol}" / f"timeframe={timeframe}" / "candles.parquet"


def available() -> list[tuple[str, str]]:
    """Every (symbol, timeframe) actually present in the lake, read from disk."""
    if not LAKE.exists():
        return []
    out = []
    for sd in sorted(LAKE.glob("symbol=*")):
        for td in sorted(sd.glob("timeframe=*")):
            if (td / "candles.parquet").exists():
                out.append((sd.name.split("=", 1)[1], td.name.split("=", 1)[1]))
    return out


def read_candles(
    symbol: str,
    timeframe: str,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
) -> list[Candle]:
    """Load candles for one symbol/timeframe, optionally windowed [start, end).

    Raises `UnsupportedTimeframeError` for a timeframe no strategy may reference, and
    `DataUnavailableError` when the pair is absent — both loudly, per the card's failure
    behaviour requirement. Never returns a partially-satisfied window silently.
    """
    if timeframe not in INTERVALS:
        raise UnsupportedTimeframeError(
            f"{timeframe!r} is not supported; StrategySpec allows {sorted(INTERVALS)}"
        )
    path = lake_path(symbol, timeframe)
    if not path.exists():
        have = available()
        raise DataUnavailableError(
            f"no candles for {symbol} {timeframe} at {path.relative_to(REPO)}. "
            f"In the lake: {have or 'nothing — run research.data.binance_download'}"
        )
    t = pq.read_table(path)
    times = t.column("open_time").to_pylist()
    cols = {c: t.column(c).to_pylist() for c in ("open", "high", "low", "close", "volume")}
    trades = t.column("trades").to_pylist()

    out = []
    for i, ts in enumerate(times):
        if start and ts < start:
            continue
        if end and ts >= end:
            continue
        out.append(Candle(ts, cols["open"][i], cols["high"][i], cols["low"][i],
                          cols["close"][i], cols["volume"][i], trades[i]))
    return out


def validate(candles: list[Candle], symbol: str, timeframe: str) -> GapReport:
    """Check spacing, ordering, duplication and OHLC self-consistency. Repairs nothing.

    The OHLC checks matter as much as the gap check and are easier to forget: a bar whose
    high is below its close is impossible, and it will not announce itself — it just makes
    one indicator slightly wrong forever.
    """
    if timeframe not in BAR_SECONDS:
        raise UnsupportedTimeframeError(f"{timeframe!r} has no known bar duration")
    step = dt.timedelta(seconds=BAR_SECONDS[timeframe])
    rep = GapReport(
        symbol=symbol, timeframe=timeframe, bars=len(candles),
        first=candles[0].open_time if candles else None,
        last=candles[-1].open_time if candles else None,
    )
    seen: set[dt.datetime] = set()
    prev: Candle | None = None
    for c in candles:
        if c.open_time in seen:
            rep.duplicates.append(c.open_time)
        seen.add(c.open_time)

        if prev is not None:
            delta = c.open_time - prev.open_time
            if delta <= dt.timedelta(0):
                rep.out_of_order.append(c.open_time)
            elif delta > step:
                missing = int(delta / step) - 1
                if missing > 0:
                    rep.gaps.append((prev.open_time, c.open_time, missing))

        hi, lo = c.high, c.low
        if hi < lo:
            rep.ohlc_violations.append((c.open_time, f"high {hi} < low {lo}"))
        for name, v in (("open", c.open), ("close", c.close)):
            if not (lo <= v <= hi):
                rep.ohlc_violations.append(
                    (c.open_time, f"{name} {v} outside [low {lo}, high {hi}]")
                )
        for name, v in (("open", c.open), ("high", hi), ("low", lo), ("close", c.close)):
            if v <= 0:
                rep.non_positive.append((c.open_time, f"{name}={v}"))
        if c.volume < 0:
            rep.non_positive.append((c.open_time, f"volume={c.volume}"))
        prev = c
    return rep


def main() -> int:
    """Report on everything in the lake. `python -m research.data.candles`"""
    pairs = available()
    if not pairs:
        print("Lake is EMPTY. Run: .venv/bin/python -m research.data.binance_download")
        return 1
    print(f"{'':<2}Lake: {LAKE.relative_to(REPO)}\n")
    worst = 0
    for sym, tf in pairs:
        rep = validate(read_candles(sym, tf), sym, tf)
        print("  " + rep.summary())
        for a, b, n in rep.gaps[:3]:
            print(f"      gap {a:%Y-%m-%d %H:%M} -> {b:%Y-%m-%d %H:%M}  ({n} bars)")
        if len(rep.gaps) > 3:
            print(f"      ... {len(rep.gaps) - 3} more gaps")
        worst = max(worst, 0 if rep.clean else 1)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
