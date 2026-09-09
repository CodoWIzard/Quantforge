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

### Implemented (B3, commit 534a598)
- `packages/strategy_schema/` — **working code, no stubs left**: pydantic models
  mirroring the JSON Schema, `clarification_questions()` walking the 8 B4 rules, and
  `compile_candidate()` which asks before it builds. Never run against a model yet.

### Python skeletons (signatures + docstrings, bodies raise NotImplementedError)
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

### Experiment 002 research artifacts — DONE 2026-09-07 (Jaedyn: B2, B4, V2)
- **B2** `experiments/002-strategy-compiler/ideas/I001–I020.json` — 20 BTC/ETH strategy
  ideas: 7 vague, 8 partial, 2 complete, 3 edge. 66 annotated missing fields.
- **B4** `experiments/002-strategy-compiler/CLARIFICATION_RULES.md` + `.json` — 8 rules,
  26 questions covering breakout, volume, exit, timeframe, risk, indicator_params,
  direction, market.
- **V2** `experiments/002-strategy-compiler/unsafe/U001–U018.json` — 18 impossible/unsafe
  requests: 13 REJECT, 1 CLARIFY, 4 COMPILE_WITH_WARNING.
- `experiments/002-strategy-compiler/RESULT.md` is written up (104 lines), NOT a blank
  template. Board items B2/B4/V2 are marked done.
- These are **research artifacts** — the corpus and expected behaviour. No model has been
  run against them yet, so Experiment 002's gate is NOT met. The compiler still raises.

### Tests — **154 passed, 38 xfailed**
- `test_contracts.py` (14) and `test_agent_contracts.py` — run today, assert the contracts
- `test_experiment_002_fixtures.py` (56) — locks the B2/B4/V2 corpus
- `test_repo_facts.py` (9) — bots must describe the repo from disk, never from memory
- Nine Appendix E catalogue files — xfail until their subsystem exists

### Infra + docs
- ADR-001..010, `.github/` templates, CI, cron/systemd for the Discord bots
- infra/ READMEs: Azure service introduction order, budget table, Terraform module plan

### Discord agent service — **running**
`services/discord-bots/` runs six personas in one process, each with its own
gateway identity: Research_Director, Strategy-Analyst, Risk-Reviewer, QA-bot,
Builder_1, Admin-bot. These are NOT the `agents/` directory — that holds
instruction drafts for a future hosted-model pipeline which has never been run.
- Chat (@mention / `/ask`) is read-only: real file reads in a scratch worktree,
  every write discarded.
- `/build <task>` is the only write path: own branch, scope check against the real
  diff, pytest, push, PR. Nothing self-merges.
- `/research <idea>` (Director only) runs the full chain automatically:
  Director frames -> Strategy-Analyst writes the StrategySpec -> Risk-Reviewer
  falsifies it -> QA-bot gates the contract -> Director gives the plain-English
  verdict. Each stage posts under its own name. Fixed five-stage sequence, one run
  at a time, aborts on a failed stage.
- Every prompt carries three fact blocks read at request time: the local tree
  (`repo_facts`), the live persona roster (`roster_facts`) and GitHub state
  (`git_facts` — commits, open PRs/issues, pushed bot branches).

## What does NOT exist yet
- No Azure resources provisioned. No Terraform applied. No resource group.
- No model endpoint or hosted agent — instructions are drafts never run against a model
- No Kraken data downloaded. No collector running. No Parquet lake.
- No PostgreSQL instance, no schema, no migrations
- **No executable logic in `risk_engine`, `exchange_contracts`, `backtester` or
  `validation`** — every body still raises NotImplementedError. (`strategy_schema` is
  the exception: B3 implemented it.)
- Do not describe implementation state from this file alone — it lags merges. The bots
  count `raise NotImplementedError` from source at request time; that scan wins.
- No backtest has ever been run. No metrics exist. Any number quoted about strategy
  performance would be fabricated — the engine has never executed.
- Experiment 002's fixtures exist but have never been run against a model (needs 001).
- No Dockerfiles written
- pydantic is not yet a dependency (add it with Experiment 002)
- `packages/exchange_contracts/symbols.py` tick sizes and min order sizes are empty —
  must be populated from the live Kraken instruments endpoint, not guessed

## Immediate next action
Experiment 001 — one model call returning structured output.
Experiment 002 — strict StrategySpec compiler against the frozen schema.

Do NOT provision Managed Redis (ADR-006). Do NOT build billing.
Do NOT start the web app before the research loop is proven (§42).

## Canonical commands
    .venv/bin/python -m pytest -q
    .venv/bin/ruff check .
    npx pyright packages research agents tests
