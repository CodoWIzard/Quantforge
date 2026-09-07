# QuantForge — current state

Last updated: 2026-09-07

## Phase
Pre-internship. Repository structure built out from Master Blueprint v2.0.
Contracts are frozen; implementation has not started.

## What exists

### Shared contracts (data-contracts/) — the interface both AIOS environments build against
- `strategy-spec.schema.json` — StrategySpec, `additionalProperties: false`, bounded risk,
  mandatory bounded exit, BTC/ETH + 1m/5m/15m only
- `market-event.schema.json` — one event shape shared by replay and live
- `run-manifest.schema.json` — full reproducibility pin, `gap_policy` excludes interpolation
- `backtest-result.schema.json` — nullable Sharpe, engine warnings, verdict block
- `openapi.yaml` — agreed HTTP surface for apps/api

### Python skeletons (signatures + docstrings, bodies raise NotImplementedError)
- `packages/strategy_schema/` — models, compiler, typed errors
- `packages/risk_engine/` — hard limits, pre-trade checks, kill switch
- `packages/exchange_contracts/` — symbols, fees, order intent
- `research/backtester/` — engine, lookahead assertions, metrics
- `research/validation/` — all nine §23 tests + verdict aggregation

### Agents (agents/)
- research-director, strategy-specialist, critic — each with instructions.md,
  tools.json (least-privilege allowlist), output.schema.json, README
- 5 evaluation fixtures from §18, scoring rubric, harness stub

### Experiment ladder (experiments/)
- All ten rungs 001–010 scaffolded with build description, exit gate and RESULT.md template

### Tests — **89 passed, 38 xfailed**
- `test_contracts.py` (14) and `test_agent_contracts.py` — run today, assert the contracts
- Nine Appendix E catalogue files — xfail until their subsystem exists

### Infra + docs
- ADR-001..010, `.github/` templates, CI, cron/systemd for the Discord bots
- infra/ READMEs: Azure service introduction order, budget table, Terraform module plan

## What does NOT exist yet
- No Azure resources provisioned. No Terraform applied. No resource group.
- No Foundry deployment, model or agent — instructions are drafts never run against a model
- No Kraken data downloaded. No collector running. No Parquet lake.
- No PostgreSQL instance, no schema, no migrations
- **No executable logic anywhere in packages/ or research/** — every function raises
  NotImplementedError. The shapes are agreed; nothing computes.
- No Dockerfiles written
- pydantic is not yet a dependency (add it with Experiment 002)
- `packages/exchange_contracts/symbols.py` tick sizes and min order sizes are empty —
  must be populated from the live Kraken instruments endpoint, not guessed

## Immediate next action
Experiment 001 — one Foundry model call returning structured output.
Experiment 002 — strict StrategySpec compiler against the frozen schema.

Do NOT provision Managed Redis (ADR-006). Do NOT build billing.
Do NOT start the web app before the research loop is proven (§42).

## Canonical commands
    .venv/bin/python -m pytest -q
    .venv/bin/ruff check .
    npx pyright packages research agents tests
