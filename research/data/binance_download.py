"""Download BTC/ETH perpetual klines from Binance's free bulk archive to Parquet.

Week 3 board card: *"[Jayden] Choose the first data source path"* and *"[Jaedyn] Save a
small BTC/ETH sample dataset with provenance notes and timeframe assumptions"*.

    .venv/bin/python -m research.data.binance_download --months 3
    .venv/bin/python -m research.data.binance_download --months 1 --symbols BTC-PERP

SOURCE: https://data.binance.vision — monthly ZIPs of CSV klines, public, no API key
and no rate limit worth managing. The REST endpoint (`fapi/v1/klines`) is capped at
1500 bars per call and would need thousands of paginated requests for the same span,
each a chance to silently skip a window. Bulk files are also immutable, so a run is
reproducible; a REST range is whatever the venue serves today.

ADR-012 names Binance as the data source. ADR-004 keeps Parquet as the lake format.

WHAT THIS DELIBERATELY DOES NOT DO
- No gap filling, no interpolation, no resampling. RunManifest's `gap_policy` excludes
  interpolation, and a downloader that quietly repairs its input destroys the evidence
  that the input was broken. Gaps are found and REPORTED by `candles.py`.
- No "latest" or partial current month: an incomplete month would land in the lake
  looking complete. Only months that have fully elapsed are fetched.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from packages.exchange_contracts.binance_symbols import (  # noqa: E402
    SYMBOLS,
    venue_interval,
    venue_symbol,
)

BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
LAKE = REPO / "data" / "lake"

#: Binance's documented kline CSV column order. The files carry no header row, so this
#: order IS the contract — a positional misread would put volume in the close column
#: and every indicator downstream would be quietly wrong.
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_base_volume", "taker_buy_quote_volume", "ignore",
]

#: The subset we keep, and the schema the lake is written with. Prices and volumes are
#: strings in the CSV; they are stored as float64 because that is what the indicator
#: layer consumes, and the exactness that matters (tick grids) lives in
#: binance_symbols.TICK_SIZE as Decimal.
SCHEMA = pa.schema([
    ("open_time", pa.timestamp("ms", tz="UTC")),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
    ("trades", pa.int64()),
])


def completed_months(count: int, today: dt.date | None = None) -> list[str]:
    """The `count` most recent FULLY ELAPSED months, oldest first, as 'YYYY-MM'.

    The current month is excluded deliberately: Binance publishes a partial file for it,
    and a partial month in the lake is indistinguishable from a complete one once the
    filename is the only label.
    """
    today = today or dt.date.today()
    y, m = today.year, today.month
    out: list[str] = []
    for _ in range(count):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y:04d}-{m:02d}")
    return list(reversed(out))


def archive_url(canonical: str, timeframe: str, month: str) -> str:
    sym, iv = venue_symbol(canonical), venue_interval(timeframe)
    return f"{BASE}/{sym}/{iv}/{sym}-{iv}-{month}.zip"


def parse_rows(raw: bytes) -> list[dict]:
    """CSV bytes -> kline dicts, tolerating Binance's occasional header row.

    Some months ship a header line and some do not (it appeared partway through 2025).
    Sniffing one field beats assuming either way; assuming cost us a silently dropped or
    silently corrupt first bar depending on which guess was wrong.
    """
    rows: list[dict] = []
    reader = csv.reader(io.StringIO(raw.decode()))
    for rec in reader:
        if not rec or len(rec) < len(KLINE_COLUMNS) - 1:
            continue
        if not rec[0].strip().lstrip("-").isdigit():
            continue  # header line
        d = dict(zip(KLINE_COLUMNS, rec, strict=False))
        ts = int(d["open_time"])
        # Binance switched open_time from ms to us in some 2025+ files. A microsecond
        # stamp read as milliseconds lands in the year 57000 and every gap check passes
        # vacuously, so normalise on magnitude rather than trusting the unit.
        if ts > 10**14:
            ts //= 1000
        rows.append({
            "open_time": ts,
            "open": float(d["open"]),
            "high": float(d["high"]),
            "low": float(d["low"]),
            "close": float(d["close"]),
            "volume": float(d["volume"]),
            "trades": int(float(d["trades"])),
        })
    return rows


def fetch_month(canonical: str, timeframe: str, month: str, timeout: int = 90) -> list[dict]:
    """Download and parse one monthly archive. Returns [] if the venue has no such file."""
    url = archive_url(canonical, timeframe, month)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 - constant https host
            blob = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"    {month}  NOT PUBLISHED (404) — skipped, not invented")
            return []
        raise
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = z.namelist()[0]
        rows = parse_rows(z.read(name))
    print(f"    {month}  {len(rows):>7,} bars  ({len(blob) / 1e6:.1f} MB zip)")
    return rows


def write_parquet(rows: list[dict], canonical: str, timeframe: str) -> Path:
    """Write one symbol+timeframe to the lake, partitioned by neither — one file per pair.

    Small enough to stay one file at Month-1 scale; the partition decision belongs with
    the collector (Experiment 008), not with a sample-dataset script.
    """
    out = LAKE / f"symbol={canonical}" / f"timeframe={timeframe}"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "candles.parquet"
    table = pa.Table.from_pydict(
        {
            "open_time": pa.array([r["open_time"] for r in rows], pa.timestamp("ms", tz="UTC")),
            **{
                c: pa.array([r[c] for r in rows], pa.float64())
                for c in ("open", "high", "low", "close", "volume")
            },
            "trades": pa.array([r["trades"] for r in rows], pa.int64()),
        },
        schema=SCHEMA,
    )
    pq.write_table(table, path, compression="snappy")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--months", type=int, default=3, help="completed months back (default 3)")
    ap.add_argument("--symbols", nargs="*", default=sorted(SYMBOLS), help="canonical names")
    ap.add_argument("--timeframes", nargs="*", default=["1m", "5m", "15m"])
    a = ap.parse_args(argv)

    months = completed_months(a.months)
    print(f"Binance USD-M bulk archive (ADR-012)\nmonths: {months[0]}..{months[-1]}\n")

    written: list[tuple[str, str, int, Path]] = []
    for sym in a.symbols:
        for tf in a.timeframes:
            print(f"  {sym} {tf}")
            rows: list[dict] = []
            for mo in months:
                rows.extend(fetch_month(sym, tf, mo))
            if not rows:
                print("    NOTHING WRITTEN — no month returned data")
                continue
            rows.sort(key=lambda r: r["open_time"])
            path = write_parquet(rows, sym, tf)
            written.append((sym, tf, len(rows), path))

    print(f"\n{'symbol':<10} {'tf':<4} {'bars':>10}  path")
    for sym, tf, n, path in written:
        print(f"{sym:<10} {tf:<4} {n:>10,}  {path.relative_to(REPO)}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
