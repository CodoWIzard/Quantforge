# Data contracts

Blueprint §40: *"Contracts come before parallel implementation: StrategySpec JSON schema,
market-event schema, backtest result schema and API OpenAPI contracts."*

These four schemas are the frozen interface between the two AIOS environments and between
the AI layer and the deterministic engine. They exist so Developer A and Developer B can
build against the same shapes without reading each other's code.

| File | Contract | Consumed by |
|---|---|---|
| `strategy-spec.schema.json` | The immutable strategy definition (ADR-003) | strategy-schema, backtester, paper-executor |
| `market-event.schema.json` | One normalised market observation | market-collector, backtester, paper-executor |
| `backtest-result.schema.json` | Machine-readable run output | backtester, validation, critic agent |
| `run-manifest.schema.json` | Everything needed to reproduce a run (§21 step 2) | backtester, PostgreSQL `data_manifests` |
| `openapi.yaml` | The HTTP surface of apps/api | apps/web, agent tools |

## Change rules

- A **breaking** change to any file here requires a dedicated issue **and** an ADR, plus
  agreement from both owners (§40). It is never a drive-by edit inside a feature PR.
- Additive optional fields are non-breaking and may ship with the PR that needs them.
- Every schema carries `$id` with a version segment. Bump it on breaking change; do not
  silently redefine an existing version.
- AI agents emit *candidates* against these schemas. Validation is deterministic and
  happens in Python — a schema-invalid payload is an error, never a defaulted value.
