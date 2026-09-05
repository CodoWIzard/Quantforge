# QuantForge

AI-assisted trading strategy research, validation and controlled paper execution.

Users describe or upload trading ideas. AI turns them into explicit experiments.
Deterministic Python backtests and stress-tests them. An independent AI critic
challenges the evidence. Approved strategies deploy into controlled paper trading.

**This is not an AI that knows the market.** It is a research-and-control system that
makes systematic trading research accessible without requiring the user to assemble their
own data pipelines, backtesters, risk controls and execution infrastructure.

## Status
Pre-build. Repository scaffolded from Master Blueprint v2.0 (8 August 2026).
Five-month software development internship, two developers.

## Scope
- BTC and ETH perpetual futures, Kraken demo environment
- Intraday, roughly 1m to 15m. No HFT.
- Paper/demo execution only
- Azure + Microsoft Foundry

## Start here
| File | Purpose |
|---|---|
| `AI_PROJECT_CONTEXT.md` | Architecture rules and shared contracts |
| `CURRENT_STATE.md` | What actually exists right now |
| `NEXT_TASKS.md` | Experimental ladder + five-month roadmap |
| `KNOWN_ISSUES.md` | Open questions, risks, non-goals |
| `AGENTS.md` | Rules for AI agents working in this repo |
| `docs/decisions/` | ADR-001 .. ADR-010 |
| `docs/source/` | The Master Blueprint v2.0 document |

## Layout
```
apps/web            Next.js + TypeScript client
apps/api            Python FastAPI backend
services/           market-collector, paper-executor
packages/           strategy-schema, risk-engine, exchange-contracts
research/           backtester, validation
agents/             research-director, strategy-specialist, critic, evals
infra/terraform     Azure infrastructure as code
data-contracts/     MarketEvent, BacktestResult schemas
experiments/        Numbered spikes 001-010
tests/              Test suites
```

## Core principle
Build evidence in this order:

strict strategy representation → deterministic backtest → adversarial validation →
controlled paper execution → polished SaaS

The Azure/AI architecture serves that loop. It is not the project.

## Immediate next action
Experiment 001 (one Foundry structured-output call) and Experiment 002 (StrategySpec
compiler), in `experiments/`. Do not provision Managed Redis, do not build billing,
do not start the web interface until that loop is convincing.
