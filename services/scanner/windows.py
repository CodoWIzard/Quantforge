"""Scan windows.

The original's KZ_SCHEDULE with its backtest note preserved: scanning only at
these five windows beat adding :30 mid-scans (76.7% WR / 0.61R vs 61.1% / 0.03R,
Jan-Jul 2026). That result is inherited evidence from the BTC bot, not a
QuantForge run - do not cite it as this project's finding.

Windows are UTC. The original derived a local label with a hand-rolled
`2 if 3 <= month <= 10 else 1` DST guess, which is wrong on the changeover
weekends; zoneinfo is used here instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Amsterdam")

SCHEDULE_EVIDENCE = (
    "Inherited from the BTC kill-zone scanner backtest (Jan-Jul 2026): "
    "KZ-only 76.7% WR / +0.61R vs KZ+mid-scans 61.1% / +0.03R. "
    "Not reproduced in QuantForge; no RunManifest."
)


@dataclass(frozen=True)
class Window:
    hour: int
    minute: int
    name: str

    @property
    def minutes(self) -> int:
        return self.hour * 60 + self.minute


WINDOWS: tuple[Window, ...] = (
    Window(1, 0, "Asian"),
    Window(8, 0, "London"),
    Window(10, 0, "LonMid"),
    Window(13, 30, "NY_AM"),
    Window(17, 30, "NY_PM"),
)


def current_window(now: datetime) -> Window | None:
    """The window this instant belongs to, or None if outside every window.

    The original matched on hour alone, so a 13:00 run was labelled NY_AM even
    though NY_AM opens 13:30 - the log then misattributed the session.
    """
    now = now.astimezone(UTC)
    return next(
        (w for w in WINDOWS if w.hour == now.hour and w.minute == now.minute), None
    )


def next_window(now: datetime) -> tuple[Window, timedelta]:
    """The next window and how long until it."""
    now = now.astimezone(UTC)
    now_mins = now.hour * 60 + now.minute
    for w in WINDOWS:
        if w.minutes > now_mins:
            return w, timedelta(minutes=w.minutes - now_mins)
    return WINDOWS[0], timedelta(minutes=(24 * 60 - now_mins) + WINDOWS[0].minutes)


def local_label(now: datetime) -> str:
    """Local Amsterdam time, DST handled by the tz database."""
    local = now.astimezone(LOCAL_TZ)
    return f"{local:%H:%M} {local:%Z}"
