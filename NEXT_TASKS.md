# Next tasks

Derived from blueprint §43 (experimental ladder) and §44 (five-month delivery plan).
An experiment is finished when its **exit gate** is demonstrated and recorded in its
`RESULT.md` — not when the code looks done.

## Now — the two the blueprint names as immediate

### Experiment 001 — Model call — **DONE 2026-09-28, gate MET**
`experiments/001-model-call/run_001.py` calls one model via the hermes CLI and returns
structured JSON. Auth, logging and cost visibility demonstrated; tokens/cost from
`--usage-file`. Never needed Azure or Key Vault — the local CLI was the endpoint.
Exposed and fixed F-005 (host-profile context leaking into prompts, ADR-013); the
script now fails unless the backend can answer UNKNOWN.

### Experiment 002 — Strategy compiler
Messy hypothesis → schema-valid StrategySpec; the agent asks for what is missing.
**Gate:** 10–20 test prompts produce **no silently invented parameters**.
Work: add pydantic, implement `packages/strategy_schema/compiler.py`, un-xfail
`tests/test_strategy_compiler.py`, write the first 20 eval fixtures.

## Then, in ladder order

| # | Experiment | Exit gate |
|---|---|---|
| 003 | Local backtest | Known strategy results are reproducible |
| 008 | Live collector | Reconnect/gap/duplicate tests pass |
| 004 | Critic loop | Critic catches intentionally planted weak strategies |
| 005 | Containerise | Same result local and in container |
| 006 | Azure Job | One API call → Azure job → stored result |
| 007 | Persistence | Experiment can be reopened and reproduced |
| 009 | Paper execution | End-to-end demo trade + reconciliation + kill switch |
| 010 | SaaS shell | A new user completes the workflow without CLI |

## Five-month plan (§44)

| Weeks | Focus | Exit gate |
|---|---|---|
| 1–2 | Scope + experiments | Architecture baseline, eval fixtures, model/compiler spike, approved data contracts |
| 3–4 | Data foundation | Binance import + live collection, Blob/Parquet layout, quality checks, replay fixture |
| 5–6 | Strategy representation | Guided clarification, StrategySpec versions, deterministic compiler, schema tests |
| 7–8 | Backtest engine | Fees/funding/slippage, reproducible trades/metrics, containerised job |
| 9–10 | Agent research loop | Director + specialist + critic, traces, first evaluation suite |
| 11–12 | Validation | Out-of-sample, sensitivity, regime, delay, cost stress; verdict framework |
| 13–14 | Risk + persistence | PostgreSQL, risk engine, approvals, audit schema, cost ledger |
| 15–16 | Paper execution | TradingView paper orders, reconciliation, pause/kill switch, monitoring |
| 17–18 | SaaS + security | Web flows, auth, tenant controls, Key Vault, CI/CD/staging |
| 19 | User testing | Beginner and technical users complete the workflow; top issues fixed |
| 20 | Finalisation | Replayable demo, docs, measured cost/evals, deployment scripts, presentation |

## Before serious build (launch checklist)
- [x] Create GitHub repo + context files
- [x] Create StrategySpec schema
- [ ] Create Azure budget + lab resource group
- [x] Prove one structured-output model call — Experiment 001, 2026-09-28, exit 0
- [ ] Download/collect initial Binance data
- [x] Write first 20 evaluation fixtures — 38 exist (20 B2 ideas + 18 V2 unsafe) plus 9
      isolation controls; the deterministic harness runs them (`agents/evals/run_lab.py`).
      NOT yet run against a model. Experiment 001 is now done, so the BLOCKER is gone,
      but the model-layer harness (`run_evals.py`) is still unimplemented — the corpus
      running against a model remains an unmade claim.

## Ownership (§41, suggested)
- **Developer A — infrastructure lead:** cloud resources, Terraform, agent configs/evals,
  secrets, monitoring, deployments, cost telemetry
- **Developer B — trading/product lead:** market ingestion, StrategySpec/compiler,
  backtesting/validation, paper execution, web product
- **Both:** product scope, strategy semantics, risk rules, ADRs, final demo
