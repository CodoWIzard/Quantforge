"""Market data ingestion and deterministic candle/indicator tools (Week 3, ADR-012).

Explicit `__init__.py` rather than relying on Python's implicit namespace packages:
`research/` itself is a namespace package, and a namespace package silently merges with
any same-named directory earlier on sys.path, so an import can resolve somewhere nobody
intended and the failure appears as a missing attribute, not a missing module.
`research/backtester/` is a regular package for the same reason; stay consistent.
"""
