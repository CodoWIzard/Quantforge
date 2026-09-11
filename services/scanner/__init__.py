"""Deterministic multi-model scanner (DORMANT).

Design ported from the proven BTC kill-zone scanner: score every registered
model at fixed windows, gate on per-model thresholds, publish the full
scoreboard whether or not anything triggers, and never open a second position.

Three deliberate differences from the original, all required by AGENTS.md:

1. The model registry is EMPTY. The original imports six scoring functions from
   /root/apps/backtest_runner.py; this repository is self-contained and may not
   read that tree. Models arrive via register_model() once they exist here and
   have a RunManifest-backed backtest behind them.
2. Nothing executes. The original forks tv_paper_trade.py. paper_deploy() does
   not exist yet, so execution is a hard refusal, not a stub that half-works.
3. No cost or risk defaults. The original carries FEE_TAKER=0.0025 (Bitvavo)
   and risk 10%. "Missing values are errors, not defaults" - a scanner that
   invents a fee prices a trade that cannot happen.

ENABLED is False. Every entry point checks it.
"""

from __future__ import annotations

from .registry import ModelResult, ScanModel, register_model, registered_models
from .scanner import ENABLED, ScanReport, run_scan

__all__ = [
    "ENABLED",
    "ModelResult",
    "ScanModel",
    "ScanReport",
    "register_model",
    "registered_models",
    "run_scan",
]
