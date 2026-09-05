# ADR-003: StrategySpec is the immutable contract between AI and the deterministic engine

Status: Accepted
Date: 2026-08-08 (Master Blueprint v2.0)

## Decision
StrategySpec is the immutable contract between AI and the deterministic engine.

## Rationale
The schema, not the chat wording, is the contractual bridge. An agent must not modify a spec in memory and continue trading.

## Consequences
Any rule change produces a NEW version requiring re-validation and re-approval before deployment.

## Source
Master Blueprint v2.0, Appendix D. See docs/source/QuantForge_Master_Blueprint_v2.0.docx
