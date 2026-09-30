# BTC/ETH sample dataset — provenance and timeframe assumptions

Week 3 board card: *"[Jaedyn] Save a small BTC/ETH sample dataset with provenance notes
and timeframe assumptions"*.

Read this before quoting any number computed from the lake.

## Venue: Binance, not Kraken — and why the card says otherwise

The Week 3 card says *"Kraken OHLCVT/downloadable history or another free BTC/ETH
source"*. It was written 2026-09-02. **ADR-012 (Accepted, 2026-09-11) supersedes it:**
market data comes from Binance, paper execution from TradingView, and *"Kraken is not a
venue for this project. Not for data, not for execution, not as a fallback."*

The card is older than the decision, so this work follows the ADR, per AGENTS.md
("If a proposed change conflicts with an ADR, STOP and raise it"). The card's own wording
allows it — *"or another free BTC/ETH source"*. **Flagged for Jaedyn/Jayden: if you want
Kraken after all, this needs an ADR-014 amending ADR-012, not a quiet switch.**

`packages/exchange_contracts/symbols.py` still holds Kraken symbols and is deliberately
left stale. The Binance vocabulary is a SEPARATE module, `binance_symbols.py`.

### The concrete cost of not hand-translating

Ticks were read from Binance's own instrument list. Had anyone renamed `PF_XBTUSD` to
`BTCUSDT` and kept the numbers:

| canonical | Kraken tick (stale) | Binance tick (real) | error |
|---|---|---|---|
| BTC-PERP | 1.0 | 0.10 | 10x too coarse |
| ETH-PERP | 0.1 | 0.01 | 10x too coarse |

A 10x-coarse price grid fabricates fills at prices that never traded, and nothing
downstream would have complained.

## Source

| | |
|---|---|
| Archive | `https://data.binance.vision/data/futures/um/monthly/klines` |
| Market | Binance USD-M **perpetual** futures (`contractType: PERPETUAL`) |
| Instruments | `BTCUSDT`, `ETHUSDT` — canonical `BTC-PERP`, `ETH-PERP` |
| Instrument metadata | `https://fapi.binance.com/fapi/v1/exchangeInfo`, fetched 2026-09-30 |
| Auth | None. Public, no API key, no rate limit worth managing. |
| Downloaded | 2026-09-30 |
| Span | 2026-06-01 00:00 UTC → 2026-08-31 23:59 UTC (3 complete months) |
| Format | Parquet, snappy, `data/lake/symbol=<canonical>/timeframe=<tf>/candles.parquet` |

Bulk monthly files were chosen over `fapi/v1/klines` deliberately: the REST endpoint caps
at 1500 bars per call, so this span would need thousands of paginated requests, each a
chance to silently skip a window. Bulk files are immutable, so a run is reproducible; a
REST range is whatever the venue serves today.

## What is in the lake

| symbol | timeframe | bars | quality |
|---|---|---|---|
| BTC-PERP | 1m | 132,480 | CLEAN |
| BTC-PERP | 5m | 26,496 | CLEAN |
| BTC-PERP | 15m | 8,832 | CLEAN |
| ETH-PERP | 1m | 132,480 | CLEAN |
| ETH-PERP | 5m | 26,496 | CLEAN |
| ETH-PERP | 15m | 8,832 | CLEAN |

336,576 bars, ~14 MB. CLEAN = zero gaps, zero duplicate timestamps, zero out-of-order
bars, zero OHLC violations, zero non-positive values, verified by
`research/data/candles.py`. Counts are arithmetically checkable: 15m over June =
30 × 96 = 2,880; July and August = 31 × 96 = 2,976 each.

Reproduce the audit:

    .venv/bin/python -m research.data.candles

## Timeframe assumptions — the ones that would silently corrupt results

1. **Only 1m / 5m / 15m exist here, because only those are legal.** `StrategySpec`
   permits exactly these, so `binance_symbols.INTERVALS` maps only these three. A 1h file
   in the lake would be data no strategy may reference, and someone would use it anyway.
2. **`open_time` is the bar's OPEN, in UTC, millisecond precision, timezone-aware.** A bar
   stamped 12:00 on 15m covers [12:00, 12:15). Treating the stamp as the CLOSE shifts
   every signal one bar early and is indistinguishable from a profitable edge.
3. **No partial current month.** Only fully-elapsed months are fetched. Binance publishes
   a partial file for the running month, and a partial month is indistinguishable from a
   complete one once the filename is the only label.
4. **Unit normalisation is by magnitude, not trust.** Binance moved `open_time` from ms to
   µs in some 2025+ files. A µs stamp read as ms lands in the year 57000, where every gap
   check passes vacuously. The parser divides when the value exceeds 10^14.
5. **Header rows are sniffed, not assumed.** Some months ship a CSV header, some do not.
   Assuming either way costs a dropped or a corrupt first bar depending on the guess.
6. **Prices are float64; tick grids are Decimal.** Candle OHLCV is float64 because that is
   what the indicator layer consumes. Exactness that matters — tick and step sizes — lives
   in `binance_symbols` as `Decimal`, since 0.01 has no exact binary form and a rounding
   step is where that bites.
7. **No gap filling. No interpolation. No resampling. Anywhere.** ADR-004's `gap_policy`
   excludes interpolation. `candles.validate()` REPORTS defects and repairs nothing: a
   reader that forward-fills a missing bar hands the backtester a price that never traded,
   and every metric inherits that fiction with no trace. The current sample happens to be
   gap-free, which is luck, not a guarantee.
8. **Volatility is annualised on a 365-day year**, not the 252-day equity convention.
   Crypto trades continuously; using 252 would understate annual vol by ~40%.

## Independent verification

Tool outputs were cross-checked against pandas/numpy, computed separately from the tool
code, on 2026-09-30:

| quantity | tool | pandas/numpy |
|---|---|---|
| BTC 15m sma(20), last | 78801.83999999973 | 78801.84 |
| BTC 15m sma(200), last | 78346.45949999984 | 78346.4595 |
| BTC 15m vol per bar (500 bars) | 0.0018304 | 0.0018304317 |
| BTC 15m vol annualised | 34.3% | 34.2638% |
| BTC 15m volume ratio vs sma(20) | 0.38x | 0.37979935 |

A tool verified only against itself proves determinism, not correctness.

## Regenerate

    .venv/bin/python -m research.data.binance_download --months 3
    .venv/bin/python -m research.data.candles
    .venv/bin/python research/data/record_outputs.py --json research/data/runs

Parquet files are gitignored — 14 MB of reproducible derivative data does not belong in
git history. This file plus the downloader is the reproducible artefact.
