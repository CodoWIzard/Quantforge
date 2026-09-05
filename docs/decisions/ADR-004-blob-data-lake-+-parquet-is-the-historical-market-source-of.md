# ADR-004: Blob/Data Lake + Parquet is the historical market source of truth

Status: Accepted
Date: 2026-08-08 (Master Blueprint v2.0)

## Decision
Blob/Data Lake + Parquet is the historical market source of truth.

## Rationale
Raw tick/order-book history grows fast. Columnar files are cheaper, versionable and replayable; a backtest reads only the columns and partitions it needs.

## Consequences
PostgreSQL does not store bulk market history. Every RunManifest records the exact dataset version used.

## Source
Master Blueprint v2.0, Appendix D. See docs/source/QuantForge_Master_Blueprint_v2.0.docx
