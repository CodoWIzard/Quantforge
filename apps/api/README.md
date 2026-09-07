# api

Python FastAPI backend (§13): users, projects, entitlements, job orchestration, audit.

**Contract-first.** The HTTP surface is defined in `data-contracts/openapi.yaml`. Change
the contract in a reviewed PR before changing the implementation — `apps/web` and the
agent tool definitions are built against it.

## Responsibilities

- Accept and version StrategySpecs (reject invalid ones 422 — never default a field)
- Dispatch backtest/validation jobs to Container Apps Jobs (ADR-009)
- Serve results, verdicts and audit history
- Enforce entitlements and Research Credit accounting (§48)
- Record cost telemetry for every job (§50)

## Not responsible for

Calculating metrics, evaluating signals, or placing orders. It orchestrates; the
deterministic workers compute.
