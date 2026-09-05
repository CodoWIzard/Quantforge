# AGENTS.md — QuantForge

Rules for any AI agent (Hermes/AIOS, Claude Code, Copilot) working inside this repository.

## Scope discipline
This directory is SELF-CONTAINED. Do not read from or write to /root/apps, the Hermes
profile directories, or any other project on this machine. QuantForge does not share code,
data or credentials with the existing trading bots.

## Read before you write
1. AI_PROJECT_CONTEXT.md   — architecture rules and shared contracts
2. CURRENT_STATE.md        — what actually exists right now
3. NEXT_TASKS.md           — the experimental ladder and roadmap
4. docs/decisions/         — the governing ADRs
5. The assigned GitHub issue

If a proposed change conflicts with an ADR, STOP and raise it. Do not silently deviate.

## Hard boundaries
- AI never computes authoritative metrics. Python does. Never restate a number the
  backtester did not produce.
- AI never places orders. The deterministic executor does, after risk checks pass.
- Never invent an unspecified strategy parameter. Missing values are errors, not defaults.
- No secrets in code, logs, prompts, commits or Discord. Key Vault + managed identity.
- Historical market data goes to Parquet in the lake, never into PostgreSQL.
- Do not provision Azure Managed Redis (ADR-006).
- Do not start the web app before the research loop is proven (blueprint Part X, §42).

## Working method
- One owner per branch. Never edit another agent's active feature branch.
- Small coherent commits. Tests and docs land with the code, not after.
- Every backtest result must be reproducible from its RunManifest.
- Update CURRENT_STATE.md when a merged change alters shared knowledge.
- Record architecture decisions as docs/decisions/ADR-###-name.md with alternatives
  and consequences.

## Definition of done
Functional behaviour + tests + failure handling + security considerations +
logs/metrics where relevant + documentation updated.

## Anti-goals
No profit promises. No HFT claims. No real-money execution. No multi-exchange support.
No model fine-tuning. See KNOWN_ISSUES.md for the full non-goal list.
