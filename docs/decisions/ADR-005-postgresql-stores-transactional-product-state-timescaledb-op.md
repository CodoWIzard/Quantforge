# ADR-005: PostgreSQL stores transactional product state; TimescaleDB optional

Status: Accepted
Date: 2026-08-08 (Master Blueprint v2.0)

## Decision
PostgreSQL stores transactional product state; TimescaleDB optional.

## Rationale
PostgreSQL answers who owns what, which version was tested, which job ran, what verdict was approved, which orders are open.

## Consequences
TimescaleDB may be enabled for recent/derived series, but is never the source of truth for years of raw history.

## Source
Master Blueprint v2.0, Appendix D. See docs/source/QuantForge_Master_Blueprint_v2.0.docx
