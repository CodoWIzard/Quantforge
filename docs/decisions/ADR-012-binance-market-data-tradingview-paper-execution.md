# ADR-012 — Binance is the market data source; TradingView carries paper execution

Status: Accepted. Venue artefacts updated 2026-09-11.
Date: 2026-09-11
Amends: ADR-001 (BTC/ETH perpetuals on one exchange), ADR-004 (Parquet lake is the
historical source of truth — unchanged, only its upstream venue changes).

## Decision

Market data — historical candles and live prices for BTC/ETH perpetuals — comes
from **Binance**. Paper trading and demo execution run through **TradingView**.

**Kraken is not a venue for this project.** Not for data, not for execution, not
as a fallback. It was the original plan (ADR-001, ADR-002) and appears throughout
the repository's history; every such reference is stale.

ADR-004 is untouched: history still lands in Parquet in the lake and Parquet is
still what the backtester reads. Only the venue that fills the lake changes.

## Why this is written down at all

The decision was made in conversation and lived nowhere else. In the first live
four-stage `/research` run the Director wrote "Kraken demo" and "Kraken BTC perp
data" throughout — correctly, because `bots.py` line 303 and
`AI_PROJECT_CONTEXT.md` both say Kraken, and those files are what
`repo_facts()` feeds it. The agent cannot know a decision that is not on disk;
it will keep producing Kraken-flavoured specs until this file exists. Same class
of gap as ADR-011: an architecture change agreed verbally, then silently
contradicted by every generated artefact.

That is the general rule this ADR is really recording: **a venue, a contract or
a constraint that only exists in chat does not exist.** The prompt fact blocks
read the repository, so the repository is the only channel into the agents.

## Consequence: ADR-001's "ONE exchange" splits into two roles

ADR-001 narrowed scope to one exchange for a real engineering reason — one
symbol model, one fee/funding model, one order API, one data vocabulary. That
argument still holds per role, but the roles are now separate: Binance supplies
the data vocabulary, TradingView supplies the execution surface. The cost is
that data and fills no longer come from the same venue, so **a paper fill is not
evidence that the same fill was available in the data used to trigger it**.

Anything derived from fees, funding or microstructure must therefore be pinned
to the venue it came from. A backtest on Binance data that assumes TradingView
paper fills is measuring two different markets, and nothing in the current code
catches that.

## What changed, and what deliberately did not

Done, because the agents read these files and nothing else:

- `services/discord-bots/bots.py` CONTEXT — the one line that most directly
  steers every generated StrategySpec. It now names both venues, says Kraken is
  no longer one, and tells the bots to treat any Kraken reference they read in
  the repo as stale rather than authoritative.
- `AI_PROJECT_CONTEXT.md`, `README.md`, `CURRENT_STATE.md`, `NEXT_TASKS.md`,
  `KNOWN_ISSUES.md`, `packages/README.md`.
- Service and experiment READMEs: market-collector, paper-executor (including
  `adapter_kraken.py` -> `adapter_tradingview.py` in the planned layout),
  experiments 008 and 009.
- `data-contracts/market-event.schema.json` provenance example.
- Two evaluation fixtures (U007, U010) that named a Kraken account and a Kraken
  API key. A fixture naming a venue the project does not use tests the agent
  against a world that does not exist.
- ADR-002 carries an amendment note: its boundary (paper is the end of the
  internship) is unchanged; only the venue it named has moved.

Deliberately NOT changed:

- `packages/exchange_contracts/` keeps its Kraken symbols, ticks and size
  precision, now marked stale in the module docstrings. The numbers were fetched
  from the live Kraken endpoint on 2026-09-07 and are correct about Kraken; they
  are simply about a venue we no longer use. **Do not adapt this package by
  renaming.** `PF_XBTUSD` -> `BTCUSDT` is a one-line edit that silently carries
  Kraken's tick sizes and size precision into a Binance context, and a wrong tick
  size fabricates fills at prices that never existed. A Binance vocabulary is a
  NEW module built from Binance's own instrument list, beside this one.
- `tests/test_exchange_contracts.py` stays for the same reason: it guards the
  SHAPE a venue package must have (canonical scope, tick rounding, provenance,
  a live re-verification test), which is what a Binance module should copy. Its
  `-m live` check now only proves the Kraken numbers still match Kraken — it is
  not evidence about Binance.

Unchanged: paper only (ADR-002), no real money, no multi-exchange support as a
product feature. Two venues in two distinct roles is not multi-exchange support,
and this ADR is not a licence to add a third.

## Still open — an implementation question, not a venue question

The venue decision is settled and this ADR is Accepted on it. One mechanism
question remains and is tracked in KNOWN_ISSUES.md: TradingView is a charting and
alerting surface, not a matching engine, so does it **simulate** the paper fills
itself, or does it **signal** a QuantForge paper executor that simulates them?
Those are different systems with different failure modes. Experiment 009 cannot
start until it is answered, and nothing may assume one of them in the meantime —
missing values are errors, not defaults (AGENTS.md).

## Alternatives considered

**Stay on Kraken for both.** No work, and it is what every artefact already says.
Rejected: it is no longer the decision, and leaving the repository asserting it
guarantees the agents keep repeating it.

**Move data to Binance and say nothing about execution.** Rejected — it leaves
the same verbal-only gap for the execution venue that this ADR exists to close.

**Record the split now, resolve the execution mechanism next.** Chosen. The data
half is unambiguous and unblocks the collector; the execution half is named as
open rather than guessed.
