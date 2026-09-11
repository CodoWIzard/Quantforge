# ADR-011 — The Director absorbs the specialist roles

Status: Accepted, transition NOT yet executed.
Date: 2026-09-11
Supersedes: ADR-007 (Director + selected specialists + deterministic tools)

## Decision

QuantForge moves to ONE reasoning agent — the QuantForge Director — plus a layer
of deterministic Python tools. The Strategy Analyst, Risk Reviewer, QA bot and
Builder stop being separate agents; their responsibilities become Director modes
(Intake, Clarification, StrategySpec, Tool Planning, Evidence Review, Skeptical
Critic, Report) or move into deterministic validators.

## Why

The multi-agent chain was built before there was any evidence that separation
improves output quality. It costs tokens, latency, orchestration code and
debugging effort on every run. For a Month 1 prototype the goal is to prove the
research loop works at all, not to prove that multi-agent is necessary.

## Why it is NOT live yet

The contract's core promise is "AI interprets, Python computes": the Director
delegates everything numeric to eleven deterministic tools.

    get_market_data            validate_market_data     calculate_indicators
    compile_strategy_spec      run_backtest             test_parameter_sensitivity
    run_walk_forward_validation                         calculate_risk_metrics
    stress_fees_slippage_latency                        generate_research_report
    paper_deploy

As of this ADR, ZERO of the eleven exist. `compile_candidate()` in
packages/strategy_schema is the only working evidence-producing code in the
repository. research/backtester/, research/validation/ (all nine tests) and
packages/risk_engine/ are signatures whose bodies raise NotImplementedError.

Collapsing to a single Director today would delete the Risk Reviewer's
falsification pass and the QA contract gate and replace them with sixteen files
that raise NotImplementedError. That is strictly worse than what runs now: the
Director would be the only agent left, forbidden by its own contract from
computing metrics, with no tool able to compute them either.

## Precondition for execution

The tool layer lands first. A deprecated specialist may only be switched off
once the deterministic tool that replaces its judgement is implemented, tested,
and producing output pinned to a RunManifest.

Build order (dependency-first):

    1. get_market_data + validate_market_data
    2. calculate_indicators
    3. compile_strategy_spec      (wrapper over the working compile_candidate)
    4. run_backtest               + lookahead assertions
    5. calculate_risk_metrics
    6. sensitivity / walk-forward / fee-slippage-latency stress
    7. generate_research_report
    8. paper_deploy               (gated, last)

## Consequence for NEXT_TASKS.md

Experiment 004 is "Critic loop: critic catches intentionally planted weak
strategies". This ADR removes the separate critic before that gate has ever run,
so the comparison evidence the decision itself demands would never be collected.

Resolution: run 004 against the Director's internal Skeptical Critic Mode rather
than against a separate agent. The gate is unchanged — planted weak strategies
must still be caught — only the thing under test changes.

## Rule for re-adding an agent

A second agent returns only when evaluation shows it catches materially more
errors than the Director's internal critic mode plus deterministic validators.
Valid future reasons: independent critique measurably improves validation;
one responsibility carries context that pollutes the Director; production
latency needs parallelism; a different model is clearly better at one isolated
function; compliance demands independent review.

Until that evidence exists: one Director, many deterministic tools, strict
versioning, skeptical review, no AI in the trading hot path.

## Alternatives considered

**Collapse now, accept the gap.** Cheapest and fastest, and defensible if Week 2
only needs to prove the conversational loop. Rejected because the project would
lose its only working review step and gain nothing measurable in return.

**Keep the multi-agent chain.** No work required. Rejected: it was never
justified by evidence, and every run pays for it.

**Record the decision, sequence the execution.** Chosen. The architecture is
settled now, while the reasoning is fresh; the switch-off waits on the tools
that make it safe.
