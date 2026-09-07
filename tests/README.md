# Tests

Appendix E of the blueprint is the **minimum test catalogue**. `test_contracts.py` runs
today; the rest are structured placeholders that fail loudly (`xfail`) until their
subsystem exists — so an unimplemented area is visible in the test report rather than
silently absent.

| Area | Required tests | File |
|---|---|---|
| Strategy compiler | Missing parameters, invalid indicators, impossible risk values, deterministic same-input schema expectations | `test_strategy_compiler.py` |
| Data ingestion | Reconnect, duplicate event, out-of-order timestamp, gap detection, schema migration | `test_data_ingestion.py` |
| Backtester | Known fixture, no-look-ahead, fee/funding correctness, stop/target priority, reproducibility | `test_backtester.py` |
| Validation | Out-of-sample split, parameter sweep bounds, regime labels, suspicious concentration | `test_validation.py` |
| Risk engine | Max position, daily loss, stale data, duplicate order, kill switch | `test_risk_engine.py` |
| Execution | Idempotent submit, rejected order, partial fill, reconnect/reconcile, exchange mismatch | `test_execution.py` |
| Agents | Tool choice, schema adherence, injection resistance, unsupported claims, escalation | `test_agents.py` |
| Tenancy/security | Cross-tenant query attempts, secret scanning, role checks | `test_security.py` |
| Cost | Token/compute cost recorded for every job; limits applied | `test_cost.py` |

Existing suites (`test_discord_bots.py`, `test_progress_board.py`, `test_cron_jobs.py`)
cover the collaboration tooling and already pass.

## Run

    .venv/bin/python -m pytest -q
