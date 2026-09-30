# QuantForge — current state

Last updated: 2026-09-30

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
- 5 evaluation fixtures from §18 (agent-layer, not yet runnable)

### Week 3 data + tool layer — DONE 2026-09-30
- `packages/exchange_contracts/binance_symbols.py` — NEW module, read from Binance's
  own instrument list. Ticks are `Decimal`. **Kraken's BTC tick is 1.0, Binance's is
  0.10** — a 10x difference, which is why `symbols.py` stays stale and unconverted.
- `research/data/binance_download.py` — free monthly bulk archive (data.binance.vision),
  no API key. Only fully-elapsed months; normalises the ms/us `open_time` switch by
  magnitude; sniffs the optional CSV header.
- `research/data/candles.py` — reader + validator that REPORTS and never repairs. Gaps,
  duplicates, out-of-order stamps, impossible OHLC, non-positive values. Missing data
  raises `DataUnavailableError` rather than returning `[]`.
- `research/data/indicators.py` — SMA, simple/log returns, sample stdev, annualised
  volatility (365-day year), volume comparison, max drawdown. `Series` carries its
  `offset`; insufficient data raises instead of returning a shorter window.
- `research/data/tools.py` — 5 agent-facing tools, explicit allowlist, JSON-Schema
  declarations with `additionalProperties: false`, and a `ToolResult` carrying provenance
  plus a one-line citation. Failures are typed refusals naming the valid set.
- **The lake holds 336,576 real bars**, BTC/ETH x 1m/5m/15m x 2026-06..08, all verified
  gap-free. Parquet is gitignored; `research/data/DATASET_PROVENANCE.md` + the downloader
  are the reproducible artefact.
- Cross-checked against pandas/numpy computed independently (sma(20) 78801.84, annualised
  vol 34.26%, volume ratio 0.3798). A tool verified only against itself proves
  determinism, not correctness.
- **VENUE CAVEAT:** the Week 3 card says "Kraken OHLCVT" and predates ADR-012, which
  says Kraken is not a venue for this project. The ADR was followed. Reversing this
  needs an ADR-014, not a quiet switch.

### Evaluation Lab (agents/evals/) — RUNS TODAY, Week 4 card (Jaedyn, 2026-09-28)
- `rubric.json` — 8 scoring dimensions, machine-readable; `scoring.md` is the prose
  mirror and a test asserts the two agree
- `controls.json` — 9 isolation controls, each complete except one property
- `run_lab.py` — deterministic scorer over the B2/V2 corpora plus the controls.
  `--json agents/evals/runs` appends a run record. Exit 0 = critical assertions held.
- `demo_month1.py` — the four-stage demo, exits 0, labels its own seams
- `RESULTS_LOG_FORMAT.md`, `FAILURE_LOG.md`
- `tests/test_eval_lab.py` — 23 tests, all passing
- **Two layers, reported separately.** Deterministic (schema adherence, clarification
  quality, no-invented-parameter, refusal-for-the-right-reason) runs now. Model layer
  (tool usage, groundedness, criticism quality, self-review disclosure) is NOT MEASURED —
  needs a model endpoint. A deterministic pass is not agent coverage.
- **The 13/13 unsafe-refusal number is not safety evidence** (FAILURE_LOG F-001): every V2
  fixture is prose, hence under-specified, hence refused for a missing stop loss with the
  danger never examined. All 13 raise the identical error. The controls carry the evidence.
- **F-002, found by this work and now CLOSED (2026-09-28):** the 2% hard risk limit
  existed in no code path — `risk_per_trade_pct: 3.0` with `daily_loss_limit_pct: 10.0`
  compiled clean. Enforced in `risk_engine/policies.py`; see the next section.

### Platform hard limits — F-002 closed, 2026-09-28
- `risk_engine/policies.py` is now **working code**, not a skeleton. `HardLimits.
  check_risk_block(risk)` returns a `LimitBreach` per ceiling breached (all of them, not
  the first) for `risk_per_trade_pct` (2%), `daily_loss_limit_pct` (5%) and
  `max_open_positions` (5). `_check_risk_consistency` calls it BEFORE the relational
  rule and raises `ImpossibleRiskError` naming the limit.
- The rest of `risk_engine` (pre_trade, kill_switch) is still `NotImplementedError` —
  Weeks 13-14. `tests/test_risk_engine.py` stays blanket-xfail for those; the ceiling has
  its own non-xfail file `tests/test_hard_limits.py` (20 tests) so a real check is never
  reported as xfail.
- **Two ceilings, deliberately different.** The pydantic bounds (`le=5`) are the schema
  envelope — the widest value the contract can represent. `HardLimits` is the operational
  ceiling. A value between them is schema-legal and policy-illegal; that is intended, and
  it is why a breach arrives as a typed policy refusal naming the limit rather than a
  generic validator message. Do not "tidy" this into one number.
- Fixing it exposed a second hole: C002 still passed with the ceiling deleted, because its
  daily limit lets the *relational* rule catch the same input and both rules raise
  `ImpossibleRiskError`. Controls now support `expected_reason_contains` (C001/C002/C003
  pin `"platform hard limit"`), and `test_removing_the_hard_limit_fails_the_controls_
  that_test_it` is a standing mutation test. An exception class is not a mechanism.

### Experiment ladder (experiments/)
- All ten rungs 001–010 scaffolded with build description, exit gate and RESULT.md template

### Experiment 001 — DONE 2026-09-28, gate MET
- One model call via the hermes CLI returns schema-shaped JSON. Auth, logging and cost
  visibility all demonstrated; tokens and cost come from `--usage-file`, never from a
  dashboard by hand.
- The run exposed F-005 (backend leaking the host profile's personal context) and was
  re-run clean after ADR-013. Cache-write tokens for the same 3-token prompt fell from
  14,576 to 2,185.
- The script now fails unless the backend answers UNKNOWN to a question the prompt
  never answered, so "the backend was clean" is part of the gate, not a footnote.
- This unblocks the model layer of the eval lab. It does NOT mean the model layer is
  measured — that still needs the harness wired up (`run_evals.py` is unimplemented).

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

### Tests — **681 collected, 0 failures, 34 xfailed, 44 skipped** (verified 2026-09-30)
- Zero known failures. Read counts from `--junitxml`: `pytest -q` prints only progress
  dots here, so grepping stdout for "passed" silently yields nothing.
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
Builder_1, Admin-bot.
- **Backend profile (ADR-013, F-005):** every `hermes` call passes `-p quantforge`,
  a dedicated profile with no personal context. Without it the CLI inherits the
  host's sticky profile and injects that profile's trading context into the prompt —
  Experiment 001 got "the MNQ1! futures trading assistant" from a prompt naming no
  instrument. `--ignore-user-config` does NOT fix this. `default` and `futures` both
  leak. `builder.build()` takes `hermes_profile` as a required keyword.
  Live proof: `services/discord-bots/probe_isolation.py` (real model, not in tests/).
  CI proof: `tests/test_backend_isolation.py`, 9 tests over source text. These are NOT the `agents/` directory — that holds
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
- No hosted/Foundry-style agent — `agents/` instructions are drafts never run against a
  model. (A working model CALL exists: Experiment 001. The two are different things.)
- No LIVE collector running (Experiment 008). Historical Binance data IS downloaded:
  336,576 bars in `data/lake/` (gitignored, reproducible). No streaming ingest yet.
- No PostgreSQL instance, no schema, no migrations
- **No executable logic in `exchange_contracts`, `backtester` or `validation`** — every
  body still raises NotImplementedError. Two exceptions: `strategy_schema` (B3) and
  `risk_engine/policies.py` (F-002 fix, 2026-09-28). `risk_engine`'s `pre_trade` and
  `kill_switch` still raise.
- Do not describe implementation state from this file alone — it lags merges. The bots
  count `raise NotImplementedError` from source at request time; that scan wins.
- No backtest has ever been run. No metrics exist. Any number quoted about strategy
  performance would be fabricated — the engine has never executed.
- Experiment 002's fixtures exist but have never been run against a model (needs 001).
- No Dockerfiles written
- pydantic is not yet a dependency (add it with Experiment 002)
- `packages/exchange_contracts/` holds KRAKEN symbols, ticks and size precision,
  fetched 2026-09-07 from the Kraken Futures instruments endpoint. ADR-012 moved
  data to Binance and execution to TradingView, so every number in that package
  now describes a venue this project does not use. It is stale, not wrong-for-
  Kraken: do not hand-translate `PF_XBTUSD` to a Binance ticker or reuse the tick
  sizes. A Binance vocabulary must be fetched from Binance's own instrument list.
  A wrong tick size silently corrupts every simulated fill.

## Immediate next action
Wire `agents/evals/run_evals.py` to the model layer — 4 of 8 rubric dimensions are still
NOT MEASURED, and `tool_usage` became measurable for the first time now that
`research/data/tools.py` exists.
Then Experiment 002 — run the 38-fixture compiler corpus against a model.
See `agents/evals/MONTH1_CONCLUSION.md` for the ordered Month 2 list.

Do NOT provision Managed Redis (ADR-006). Do NOT build billing.
Do NOT start the web app before the research loop is proven (§42).

## Canonical commands
    .venv/bin/python -m pytest -q
    .venv/bin/ruff check .
    npx pyright packages research agents tests
