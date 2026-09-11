# ADR-012 — Binance is the market data source; TradingView carries paper execution

Status: Proposed — awaiting confirmation of the execution half (see Open question).
Date: 2026-09-11
Amends: ADR-001 (BTC/ETH perpetuals on one exchange), ADR-004 (Parquet lake is the
historical source of truth — unchanged, only its upstream venue changes).

## Decision

Market data — historical candles and live prices for BTC/ETH perpetuals — comes
from **Binance**, not Kraken. Paper trading and demo execution run through
**TradingView**.

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

## What must change, and what must not

Not yet done — this ADR records the decision, not its execution:

- `services/discord-bots/bots.py` CONTEXT: "Kraken demo" is now wrong and is the
  single line that most directly steers every generated StrategySpec.
- `AI_PROJECT_CONTEXT.md` line 13.
- `CURRENT_STATE.md` — the "no Kraken data downloaded" notes.
- `packages/exchange_contracts/` is Kraken-specific by design and stays isolated;
  a Binance vocabulary is an addition beside it, not an edit to it. Its symbol
  table was fetched from the live Kraken instruments endpoint and must not be
  hand-translated to Binance names — the same rule applies to the new one: fetch
  the live instrument list, never guess precision or tick size.

Unchanged: paper only (ADR-002), no real money, no multi-exchange support as a
product feature. Two venues in two distinct roles is not multi-exchange support,
and this ADR is not a licence to add a third.

## Open question — must be resolved before this moves to Accepted

"TradingView for paper trading/demo" is recorded as stated but is thinner than a
contract needs. TradingView is a charting and alerting surface, not a matching
engine: paper fills there are simulated against its own feed, and its usual role
in this operator's other systems is webhook alert delivery into an executor.

So the executable question is: does TradingView **simulate** the paper fills, or
does it **signal** a QuantForge paper executor that simulates them? Those are
different systems with different failure modes, and this file deliberately does
not choose between them. Missing values are errors, not defaults (AGENTS.md).

## Alternatives considered

**Stay on Kraken for both.** No work, and it is what every artefact already says.
Rejected: it is no longer the decision, and leaving the repository asserting it
guarantees the agents keep repeating it.

**Move data to Binance and say nothing about execution.** Rejected — it leaves
the same verbal-only gap for the execution venue that this ADR exists to close.

**Record the split now, resolve the execution mechanism next.** Chosen. The data
half is unambiguous and unblocks the collector; the execution half is named as
open rather than guessed.
