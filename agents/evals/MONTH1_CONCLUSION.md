# Month 1 conclusion — what works, what fails, what carries into Month 2

Week 4 board card: *"[Both] Write the Month 1 conclusion: what works, what fails, what
carries into Month 2"*.

Written 2026-09-30 from the repository's own output. Every claim below names the command
that produces it, so a reader can re-run rather than trust. **DRAFT for Jayden and Jaedyn
to sign off** — the ownership calls in "Carries into Month 2" are proposals, not decisions.

Stage 1 / Month 1's goal was *"Prove the Core Concept: turn vague trading ideas into
strict, schema-based StrategySpecs without inventing missing rules."*

**Verdict: the core concept holds, deterministically. The agent layer is unproven.**
That distinction is the single most important sentence in this document, and Month 1's
main achievement is that the repository now makes the distinction impossible to blur.

## Baseline, measured today

    .venv/bin/python -m pytest -q --junitxml=/tmp/qf.xml    # 679 tests, 0 failures
    .venv/bin/ruff check .                                  # clean
    npx pyright packages research agents tests services     # 0 errors

679 tests, 0 failures, 34 xfailed (unbuilt subsystems, deliberately marked), 44 skipped.

## What works

**1. A vague idea produces questions, not a guess.**
`packages/strategy_schema` asks 8 rules' worth of clarifying questions in ONE pass and
refuses to compile an under-specified candidate. No field is ever defaulted.

    .venv/bin/python agents/evals/demo_month1.py

**2. An answered idea compiles to a schema-valid, hashed spec with an audit trail.**
`metadata.clarifications` records that the USER supplied each value. Traceability is the
feature, not the JSON.

**3. The platform risk ceiling is enforced in code.**
`risk_engine/policies.py` returns a `LimitBreach` per ceiling breached — all of them, not
the first. Two deliberately different ceilings: pydantic `le=5` is the schema envelope,
`HardLimits` (2%/5%/5) is the operational one. A value between them is schema-legal and
policy-illegal, by design.

**4. Real market data, with deterministic tools over it.**
336,576 bars of Binance BTC/ETH perps (1m/5m/15m, 2026-06..08), verified gap-free. Five
tools — `describe_market`, `moving_average`, `realised_volatility`, `volume_spike`,
`validate_strategy_inputs` — each returning a `ToolResult` with a citation naming the call
and its bar window.

    .venv/bin/python -m research.data.candles
    .venv/bin/python research/data/record_outputs.py

Cross-checked against pandas/numpy computed independently: sma(20) 78801.84, annualised
vol 34.26%, volume ratio 0.3798 — all matching. A tool verified only against itself proves
determinism, not correctness.

**5. Bad inputs are typed refusals that name the valid set.**
Wrong symbol, venue ticker instead of canonical name, unsupported timeframe, window longer
than history, unknown tool: 8 deliberate failures, each pinned to its expected error TYPE.
A bare "invalid symbol" teaches a model nothing and it retries with another guess.

**6. The evaluation harness reports what it did NOT measure.**
`run_lab.py` prints `tool_usage`, `groundedness`, `criticism_quality` and
`self_review_disclosure` as NOT MEASURED, and labels 5 corpus ideas NOT MEASURABLE. A
dimension missing from a report reads as one that passed.

**7. A six-persona Discord research chain runs end to end**, each stage publishing under
its own identity, with scope boundaries that exclude what each persona judges or authors.

## What fails, or does not exist

**1. No backtest has ever run.** `research/backtester/` and `research/validation/` raise
`NotImplementedError`. **There is no performance number anywhere in this project, and any
that appears is fabricated.** This is the biggest gap and it is entirely expected —
blueprint §44 puts the engine in Weeks 7-8.

**2. The model layer of the eval lab is unmeasured.** The blocker (F-005) is fixed, but
`run_evals.py` is still a stub. Four of eight rubric dimensions have never been scored.

**3. Sentence -> structure does not exist.** Stage 1 of the demo is done by hand and says
so. The compiler reads structured fields; the corpus stores prose (F-006). This is the
agent's job and the agent has not been run against it.

**4. Fees are a placeholder.** Symbols and ticks are real, read from Binance's instrument
list. `0.05%/side` in the demo is invented. A wrong fee silently corrupts every simulated
fill, so this must be fetched before any cost-sensitive claim.

**5. Look-ahead is caught incidentally** (F-003, OPEN). C004 passes because
`next_bar_high` is off the indicator allowlist, not because anything reasons about
look-ahead. `lookahead.py` still raises. Right answer, wrong mechanism.

**6. Nothing is deployed.** No Azure resources, no Terraform, no PostgreSQL, no
Dockerfiles, no collector. Deliberate — blueprint §42 forbids the web app before the
research loop is proven.

## Failures worth carrying as lessons, not just fixes

Six findings in `agents/evals/FAILURE_LOG.md`. Three generalise beyond this project:

**F-001 — a 13/13 refusal rate that measured vagueness, not danger.** Every V2 unsafe
fixture is prose, hence under-specified, hence refused for a missing stop loss with the
danger never examined. All 13 raised the identical error. *A check whose output does not
vary with the property it claims to test is not testing it.* The fix was `controls.json`:
complete specs with ONE property mutated, plus a negative control.

**F-002 — the 2% risk limit was documented everywhere and enforced nowhere.** Found
immediately by the controls. Worse: after fixing it, C002 still passed with the ceiling
deleted, because a different rule caught the same input and both raised the same exception.
*An exception class is not a mechanism.* Controls now pin the reason string, and a standing
mutation test breaks the ceiling to prove the controls notice.

**F-005 — the model backend supplied facts the prompt never gave it.** A 3-token prompt
returned the operator's personal trading context. `--ignore-user-config` made it worse; the
boundary was the profile (ADR-013). *Groundedness would have scored WELL, because the
leaked facts were true.* Evidence was the cache-write token count (14,576 -> 2,185), not
the reply wording — a byte count cannot be charming.

The pattern across all three: **a metric that rewards the behaviour it exists to detect is
worse than no metric.** Every one was found by deliberately breaking something and checking
that the harness noticed.

## Carries into Month 2

Ordered by what unblocks the most. Ownership follows §41 and is a proposal.

| # | Work | Why now | Owner |
|---|---|---|---|
| 1 | Wire `run_evals.py` to the model layer | 4 of 8 dimensions unscored; the blocker is gone. Now that tools exist, `tool_usage` is measurable for the first time | Jaedyn |
| 2 | Experiment 002: run the compiler corpus against a model | 38 fixtures exist and no model has seen them; closes the sentence->structure seam | Both |
| 3 | Experiment 003: the backtester | Everything downstream of "does it make money" is blocked, and it is the one claim nobody can currently make | Jayden |
| 4 | Fetch real Binance fees | Cheap; removes the last invented number from the demo | Jayden |
| 5 | F-003: real look-ahead detection | Currently incidental; a refactor of the allowlist would silently remove it | Jaedyn |
| 6 | Resolve the TradingView paper-fill question | Experiment 009 is blocked on whether TradingView simulates fills or only signals an executor (KNOWN_ISSUES) | Both |

Deliberately NOT in Month 2: Azure provisioning, the web app, billing, Managed Redis
(ADR-006), real-money execution.

## Two process decisions worth keeping

**A decision that lives only in chat does not exist.** The `/research` chain wrote "Kraken
demo" through an entire run because `bots.py` still said Kraken while the venue decision
lived in conversation. Writing ADR-012 was necessary and not sufficient — the bots read
prompt fact blocks, not `docs/decisions/`. Every architecture change needs the ADR *and*
the line the model actually reads.

**Verify a fix three ways when one way cannot be trusted.** A source-text test cannot prove
a profile is clean; a paid live call cannot run per commit. Both layers were required to
close F-005, and the objective evidence was a token count rather than a model's wording.

## One caveat on this document

Week 3's card names Kraken as the data source. ADR-012 (Accepted, 2026-09-11) says Kraken
is not a venue for this project at all. The card predates the ADR, so the data work follows
the ADR and the card's own "or another free BTC/ETH source" clause. **If you want Kraken
after all, that needs an ADR-014 amending ADR-012 — not a quiet switch.** See
`research/data/DATASET_PROVENANCE.md`.
