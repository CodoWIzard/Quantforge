# QuantForge — current state

Last updated: 2026-09-05

## Phase
Pre-internship. Repository scaffolded from Master Blueprint v2.0. No code written yet.

## What exists
- Repository skeleton (apps/, services/, packages/, research/, agents/, infra/, docs/)
- Master Blueprint v2.0 stored at docs/source/QuantForge_Master_Blueprint_v2.0.docx
- AI_PROJECT_CONTEXT.md, NEXT_TASKS.md, KNOWN_ISSUES.md
- ADR-001 .. ADR-010 recorded as the baseline architecture decisions

## What does NOT exist yet
- No Azure resources provisioned
- No Foundry deployment or agent
- No Kraken data downloaded
- No StrategySpec schema implemented
- No backtester
- No CI

## Immediate next action (from the blueprint)
Experiment 001 — one Foundry model call returning structured output.
Experiment 002 — strict StrategySpec compiler.
Do NOT provision Managed Redis. Do NOT build billing. Do NOT start the web app.
