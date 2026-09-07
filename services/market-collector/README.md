# market-collector

Maintains Kraken WebSocket feeds and writes normalised `MarketEvent` records to the lake.

Blueprint §26, §31, Experiment 008. Exit gate: **reconnect / gap / duplicate tests pass.**

## Responsibilities

- Subscribe to candles, trades, funding (and book, later) for BTC-PERP and ETH-PERP
- Write the **raw** layer append-only, preserving provenance
- Produce the **curated** layer: cleaned, deduplicated, UTC-normalised Parquet
- Emit coverage/gap reports that `research/validation/data_audit.py` consumes

## Why it can't scale to zero

§31: an always-on collector is the one continuously running container. Everything else
is a job or scales to zero. This is the main fixed compute cost in the budget.

## Failure behaviour

Reconnect with backoff, deduplicate by sequence number, never interpolate a gap. A gap
is recorded as a gap — downstream decides whether to fail or exclude.

## Layout when implemented

    market-collector/
      collector.py      # WebSocket client, reconnect logic
      normalise.py      # venue payload -> MarketEvent
      writer.py         # Parquet partition writer (raw + curated)
      Dockerfile
