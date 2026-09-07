# Experiment 002 — result

**Status:** in progress — research artifacts complete, compiler not yet implemented
**Gate:** 10–20 test prompts produce no silent invented parameters

## Hypothesis

A messy trading hypothesis can be turned into a schema-valid StrategySpec, and every
under-specified field becomes a question rather than a guess.

## What was actually built (2026-09-07, Jaedyn: B2 / B4 / V2)

### B2 — 20 BTC/ETH strategy ideas (`ideas/I001–I020.json`)

Deliberately weighted toward under-specified input, because that is the real input
distribution and the only thing that exercises the compiler:

| Completeness | Count | Purpose |
|---|---|---|
| vague | 7 | Almost nothing measurable — "buy the dip", "when volume looks high" |
| partial | 8 | Real thresholds, load-bearing gaps (entry defined, no exit) |
| complete | 2 | Compile with zero questions — the regression anchors |
| edge | 3 | Schema-valid but semantically suspicious — must compile *with a warning* |

66 individually annotated missing fields across the corpus. `I015` is the blueprint's own
§10 reference spec, kept as the anchor that must always compile cleanly.

### B4 — Clarification rules (`CLARIFICATION_RULES.md`, `clarification_rules.json`)

8 rules, 26 questions. The five the task named — breakout, volume, exit, timeframe, risk —
plus indicator_params, direction and market, which kept surfacing while drafting B2.

Each rule carries a trigger, why it matters, the questions, an explicit **never**, and the
schema field it compiles to. Machine-readable JSON alongside the prose so the compiler can
consume the rules rather than reimplementing them.

Key decision: **conventional defaults are still invented parameters.** "I'll use the
standard RSI period" is the same failure as inventing 1.5x volume. The rules say so
explicitly, because it is the most tempting shortcut.

### V2 — Impossible and unsafe requests (`unsafe/U001–U018.json`)

18 fixtures across three categories:

| Category | Count | Expected response |
|---|---|---|
| impossible | 6 | REJECT — look-ahead, contradictory risk, out-of-scope timeframe |
| unsafe | 8 | REJECT/CLARIFY — real money, stop removal, loss-chasing, injection, mislabelled OOS |
| suspicious | 4 | COMPILE_WITH_WARNING — valid but fee-negative, 25:1 asymmetry, sample too small |

14 are critical severity. Each records the correct behaviour **and** the specific wrong
behaviour, so a model response can be scored rather than judged by vibes.

The distinction that matters: `impossible` and `unsafe` may never be answered with a
warning — U002 (enter at the day's low) and U007 (deploy with real money) are refusals.
`suspicious` cases DO compile; suppressing them would be its own failure, since the user
is entitled to run a strategy we think is weak, as long as they are told why.

## Evidence

    .venv/bin/python -m pytest tests/test_experiment_002_fixtures.py -q
    56 passed

The suite locks the corpus: idea count stays inside the 10–20 gate, ≥60% of ideas stay
under-specified, 'complete' ideas genuinely need no questions, impossible/unsafe cases are
never downgraded to warnings, and the injection / real-money / loss-chasing / look-ahead
fixtures are all present and rejecting.

## B5 + V3 executed against the implemented compiler (2026-09-07)

B3 landed, so the deterministic half of the loop can now be *run* rather than described.
Both harnesses are committed and re-runnable; neither needs a model, network or Azure.

    .venv/bin/python experiments/002-strategy-compiler/run_b5_evidence.py   # exit 0
    .venv/bin/python experiments/002-strategy-compiler/run_v3_demos.py      # exit 0

### B5 — no invented defaults

    20 ideas: 15 under-specified, 5 complete/edge
    287 clarification questions generated across the corpus
    13 REJECT-class unsafe requests: all refused
    No idea compiled with an unanswered question.

### V3 — three demos

| Demo | Shows |
|---|---|
| I002 vague | 19 questions, refuses to compile |
| I008 partial | entry specified, exit/risk missing — still blocks |
| I015 complete | 0 questions once answered; compiles and hashes |

### A real bug this surfaced

`_triggers_volume` fired on the bare word "volume", so the compiler interrogated its own
reference spec — it asked "what multiple counts as high?" about
`volume > 1.5 * sma(volume, 20)`, which already says. I015 could not compile.

Fixed: the rule now fires only when a quantified baseline *and* a multiple are absent.
Vague volume still asks. Asking a question the user already answered is its own failure —
it teaches people to skim past the questions, which is precisely what B4 exists to prevent.

### Honest limitation

**No natural language was parsed.** `compile_candidate()` takes a structured dict; turning
a sentence into that dict is the Strategy Specialist agent's job and is blocked on
Experiment 001 (Foundry, no Azure subscription yet). What is proven: the schema, the
clarification rules, the refusal behaviour and the hashing all work deterministically.

## Gate met?

- [x] 10–20 test prompts drafted (20)
- [x] Clarification rules covering the five named gap types (8 rules)
- [x] Impossible/unsafe behaviour recorded with expected responses (18)
- [ ] **Prompts actually run against a model** — blocked on Experiment 001 (Foundry)
- [ ] Compiler implemented (`packages/strategy_schema/compiler.py` still raises)

The gate is *"prompts produce no silent invented parameters"*. The corpus and the expected
behaviour now exist and are enforced. Proving the behaviour needs a live model, so the
gate is **not yet met** — this is the input to it, not the result.

## What surprised us

Three of the twenty "ideas" turned out to be schema-valid but economically dead — a 0.15%
target on 1m BTC cannot survive round-trip fees. The compiler will happily accept them.
That created a third response class nobody had planned for: `COMPILE_WITH_WARNING`. A
binary accept/reject would have been wrong, and we only found it by writing real examples
instead of reasoning about the schema in the abstract.

Also: the task named five gap types, drafting surfaced eight. `indicator_params` in
particular is the sneakiest — "RSI below 30" reads complete until you notice the period is
missing and RSI(9) vs RSI(21) trade differently.

## Decision

Proceed. B2/B4/V2 are done as research artifacts. The remaining work on 002 is the
compiler itself (B3, Jayden) plus a live model run, which needs 001 first.

## Measured cost

| Item | Value |
|---|---|
| Model tokens (in/out) | 0 — no model called yet |
| Compute seconds | negligible (fixture authoring) |
| Storage touched | ~40 KB of JSON fixtures |
