# QuantForge — shared AI project context

Read this file FIRST at the start of any work session, together with CURRENT_STATE.md
and the issue you are assigned. The Master Blueprint v2.0 is the source of truth:
docs/source/QuantForge_Master_Blueprint_v2.0.docx

## Product identity
AI-assisted trading strategy research, validation and controlled PAPER execution.
Not a prediction engine. The product value is rigorous, auditable, reproducible research —
including the ability to REJECT a bad strategy.

## Current scope (internship baseline)
- BTC and ETH perpetual futures, ONE exchange (Kraken / Kraken derivatives demo)
- Intraday timeframes, roughly 1m to 15m. No HFT.
- Paper/demo execution only. No public real-money execution.
- Cloud direction: Microsoft Azure + Microsoft Foundry
- Two developers, separate AIOS environments, 5 months

## Architecture rules (non-negotiable)
- Historical market data      -> Azure Blob / Data Lake + Parquet
- Product/application state   -> Azure PostgreSQL Flexible Server
- Redis                       -> optional local hot cache ONLY; no Azure Managed Redis in MVP
- AI                          -> interpretation, clarification, planning, criticism, explanation
- Python / deterministic svc  -> all calculations, metrics, risk, signals, execution
- AI is NEVER in the deterministic trading hot path
- AI NEVER computes authoritative metrics
- The approved StrategySpec version is immutable and is the source of truth for execution
- The system fails CLOSED: stale data, invalid rules, failed risk checks => no new orders
- No secrets in code, logs, prompts or Discord

## Shared contracts (define before parallel implementation)
- StrategySpec schema          (packages/strategy-schema)
- MarketEvent schema           (data-contracts)
- BacktestResult schema        (data-contracts)
- API OpenAPI contract         (apps/api)
A breaking contract change requires a dedicated issue + ADR + both owners' agreement.

## Current ADRs
See docs/decisions/. ADR-001 .. ADR-010 are the governing baseline decisions.

## AIOS collaboration rules
- GitHub is the control plane. Discord is notification only, never project memory.
- Read the current issue + linked ADRs before editing anything.
- One owner per branch. Never two AIOS on the same feature branch.
- All work lands via PR with cross-review. CI must pass.
- Security/risk changes require both humans.

## Definition of done
Tests + docs + security considerations + observability + reproducibility.

## Ownership split (suggested, not a wall)
- Developer A — Azure/Foundry lead: Azure resources, Terraform, Foundry agents/evals,
  secrets, monitoring, deployments, cost telemetry.
- Developer B — trading/product lead: market ingestion, StrategySpec/compiler,
  backtesting/validation, paper execution, web product.
- Both: product scope, strategy semantics, risk rules, architecture ADRs, final demo.

## If you remember only one thing
Build evidence in this order:
strict strategy representation -> deterministic backtest -> adversarial validation ->
controlled paper execution -> polished SaaS.
The Azure/AI architecture serves that loop. It is not the project.
