# ADR-009: Container Apps Jobs for finite backtests and validation sweeps

Status: Accepted
Date: 2026-08-08 (Master Blueprint v2.0)

## Decision
Container Apps Jobs for finite backtests and validation sweeps.

## Rationale
Backtests are finite jobs, not always-running web processes. Jobs isolate CPU/memory work and bill only for duration.

## Consequences
Only the market collector runs continuously. API and workers scale to zero where possible.

## Source
Master Blueprint v2.0, Appendix D. See docs/source/QuantForge_Master_Blueprint_v2.0.docx
