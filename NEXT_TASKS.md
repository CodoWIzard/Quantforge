# QuantForge — next tasks

## Before serious build (launch checklist)
- [ ] Create GitHub repo + push context files
- [ ] Create Azure budget + lab resource group (budget alerts on day one)
- [ ] Prove one Foundry structured-output call        (Experiment 001)
- [ ] Create StrategySpec schema                      (Experiment 002)
- [ ] Download/collect initial Kraken BTC/ETH data
- [ ] Write first 20 evaluation fixtures

## Experimental ladder (each has a hard exit gate)
| # | Build | Exit gate |
|---|-------|-----------|
| 001 | Local Python script calls one Foundry model, structured output | Reliable auth, logging, cost visibility |
| 002 | Messy hypothesis -> schema-valid StrategySpec, agent asks for missing info | 10-20 test prompts, zero silently invented parameters |
| 003 | Python reads small BTC dataset -> trades + metrics | Known strategy results reproducible |
| 004 | Foundry critic receives structured results, requests robustness tests | Critic catches deliberately planted weak strategies |
| 005 | Backtester runs from Docker with input manifest -> output JSON | Same result local and in container |
| 006 | Container Apps Job runs a backtest, persists artifacts | One API call -> Azure job -> stored result |
| 007 | PostgreSQL run metadata + Blob artifacts | Experiment can be reopened and reproduced |
| 008 | Kraken WebSocket collector writes clean live data | Reconnect / gap / duplicate tests pass |
| 009 | Approved StrategySpec triggers Kraken demo orders | End-to-end demo trade + reconciliation + kill switch |
| 010 | Web app wraps the working core | New user completes whole workflow without CLI |

## Five-month plan
| Weeks | Focus | Exit gate |
|-------|-------|-----------|
| 1-2   | Scope + experiments | Architecture baseline, eval fixtures, Foundry + compiler spike, approved data contracts |
| 3-4   | Data foundation | Kraken import + live collection, Blob/Parquet layout, quality checks, replay fixture |
| 5-6   | Strategy representation | Guided clarification, StrategySpec versions, deterministic compiler, schema tests |
| 7-8   | Backtest engine | Fees/funding/slippage, reproducible trades/metrics, containerised job |
| 9-10  | Foundry research loop | Director + specialist + critic, traces, first evaluation suite |
| 11-12 | Validation | Out-of-sample, sensitivity, regime, delay, cost stress; verdict framework |
| 13-14 | Risk + persistence | PostgreSQL, risk engine, approvals, audit schema, cost ledger |
| 15-16 | Paper execution | Kraken demo orders, reconciliation, pause/kill switch, monitoring |
| 17-18 | SaaS + security | Web flows, auth, tenant controls, Key Vault, CI/CD/staging |
| 19    | User testing | Beginner + technical users complete full workflow |
| 20    | Finalisation | Replayable demo, docs, measured costs/evals, deployment scripts, presentation |

## Budget envelope (5 months, planning ranges not quotes)
| Category | Range |
|---|---|
| Foundry models / agents / evals | EUR 100-500 |
| Container Apps + Jobs | EUR 75-150 |
| PostgreSQL | EUR 0-80 |
| Blob / Data Lake | EUR 10-50 |
| Key Vault, monitoring, registry, misc | EUR 10-50 |
| Managed Redis | EUR 0 (excluded) |
| Domain / incidental | EUR 10-25 |
| **Total** | **~EUR 205-855**, target EUR 300-500 |
