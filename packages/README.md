# Packages

Shared libraries imported by services, research and apps.

| Package | Owns |
|---|---|
| `strategy_schema/` | StrategySpec models, the compiler, typed compile errors (ADR-003) |
| `risk_engine/` | Hard limits, pre-trade checks, kill switch. No AI in this package, ever |
| `exchange_contracts/` | Kraken vocabulary: symbols, fees, order intent — **stale**, ADR-012 dropped Kraken; a Binance package goes beside it |

## Naming deviation from blueprint §38 — deliberate

§38 writes these as `strategy-schema/`, `risk-engine/`, `exchange-contracts/`. Python
cannot import a module with a hyphen in its name (`import strategy-schema` is a syntax
error), so the directories use underscores. The distribution names in `pyproject.toml`
may still use hyphens — that is the normal Python convention, where
`pip install strategy-schema` provides `import strategy_schema`.

This is the only place the repo intentionally departs from the blueprint's literal
layout. Everything else follows §38 exactly.

## Status

Every function currently raises `NotImplementedError`. The signatures, docstrings and
rationale are the agreed contract; the bodies land with their experiments (002 for the
compiler, 007–016 weeks for risk and execution).
