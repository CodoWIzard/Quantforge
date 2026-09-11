# Experiment 008 — live collector

**Target window:** Weeks 3-4
**Status:** not started

## Build

Binance WebSocket collector writes clean live data (ADR-012; was Kraken).

## Exit gate

> Reconnect/gap/duplicate tests pass.

This is the only thing that decides whether the experiment is finished. Not "the code
runs" — the gate, demonstrated and recorded.

## Method

1. Write down what you expect to happen *before* running it.
2. Build the smallest thing that can test the gate.
3. Run it. Record the actual result in `RESULT.md`, including what surprised you.
4. If the gate fails, that is a finding — write it down rather than quietly moving on.

## Cost

Record model tokens, compute seconds and any storage touched (§50). Even a throwaway
experiment feeds the cost ledger, because pricing only becomes credible after hundreds
of representative jobs (§48).

## Do not

- Promote this code into `packages/` or `research/` without a reviewed PR and tests.
- Expand scope beyond the gate above. Extra ideas go in `NEXT_TASKS.md`.
