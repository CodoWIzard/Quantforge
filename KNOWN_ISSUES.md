# QuantForge — known issues and open questions

## Open questions (need a decision before the relevant phase)
- TradingView paper execution (ADR-012): does TradingView SIMULATE the fills, or does it
  only SIGNAL a QuantForge paper executor that simulates them? TradingView is a charting
  and alerting surface, not a matching engine. These are different systems with different
  failure modes and Experiment 009 cannot start until it is settled.
- Binance access from the Netherlands: confirm which Binance entity and API surface are
  usable, and whether historical klines and the live WS feed come from the same one.
- Data venue and execution venue are now different (Binance vs TradingView). Nothing in
  the codebase currently detects a fill being credited against data that never showed it.
  Decide whether reconciliation enforces that or merely reports it.
- (Closed by ADR-012: the Kraken demo/derivatives account question. Kraken is no longer
  a venue for this project. `packages/exchange_contracts` still holds Kraken numbers.)
- Azure subscription: student credits vs paid? Determines PostgreSQL and Container Apps cost.
- Which model deployments and regions are actually available to the subscription.
- Backtest engine: constrained internal Python engine first, or adopt LEAN early?
  Blueprint says internal first; revisit if order semantics outgrow it.

## Known risks carried from the blueprint
| Risk | Mitigation |
|---|---|
| AI produces inconsistent StrategySpecs | Strict schema, clarification policy, eval fixtures, versioned prompts |
| Backtest looks better than reality | Fees/funding/slippage, delay tests, out-of-sample, paper drift comparison |
| Data gaps / corruption | Timestamp + sequence checks, raw provenance, fail closed, replay fixtures |
| Scope explosion | BTC/ETH + one exchange + paper only; backlog everything else |
| Cloud/AI cost creep | Budgets, cost ledger, model routing, finite jobs, no Managed Redis |
| Agents overuse tools/secrets | Tool allowlists, Key Vault, least privilege, no exec tool for research agents |
| Two AIOS environments diverge | Context files, ADRs, contracts, issues/PRs, cross-review |
| Regulatory complexity blocks live launch | Internship stays paper-only; legal review before any live product |

## Non-goals (do not build these)
- No promise of profitable or superior trading performance
- No HFT or millisecond execution claims
- No multi-exchange / multi-asset-class support
- No public real-money automated trading
- No institutional market-data redistribution
- No custom model training program
- No Azure Managed Redis unless a benchmark proves a real bottleneck
