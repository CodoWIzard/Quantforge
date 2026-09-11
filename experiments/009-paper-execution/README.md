# Experiment 009 — paper execution

**Target window:** Weeks 15-16
**Status:** not started

## Build

Approved StrategySpec triggers deterministic TradingView paper orders (ADR-012;
was Kraken demo). ADR-012 leaves one thing undecided that this experiment must
settle before it starts: whether TradingView simulates the fill itself or only
signals a QuantForge executor that does.

## Exit gate

> End-to-end demo trade + reconciliation + kill switch.

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
