# ADR-006: Azure Managed Redis is excluded from the MVP

Status: Accepted
Date: 2026-08-08 (Master Blueprint v2.0)

## Decision
Azure Managed Redis is excluded from the MVP.

## Rationale
The entry managed tier is disproportionately expensive for a two-person MVP, and RAM is the wrong medium for long history.

## Consequences
Local open-source Redis for development only. Managed Redis revisited only after a measured bottleneck.

## Source
Master Blueprint v2.0, Appendix D. See docs/source/QuantForge_Master_Blueprint_v2.0.docx
