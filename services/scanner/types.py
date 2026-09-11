"""Candle type shared by the scanner.

Deliberately not a dict. The original passed dicts of floats between six
scoring functions; a typo in a key surfaced as a KeyError deep inside a model,
or worse, as a silently missing field.

`closed` is the field that matters most. See loader.drop_unclosed().
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool

    @property
    def open_time(self) -> datetime:
        return datetime.fromtimestamp(self.open_time_ms / 1000, tz=UTC)

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"high {self.high} below low {self.low}")
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"open {self.open} outside [{self.low}, {self.high}]")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"close {self.close} outside [{self.low}, {self.high}]")
        if self.volume < 0:
            raise ValueError(f"negative volume: {self.volume}")
