"""Evaluation harness: run fixtures against an agent, score, report.

§17 step 3 - every run is traced: model, prompt version, tool calls, arguments, outputs,
retries, latency and cost. Without traces you cannot systematically improve reliability,
so the harness records them even for passing runs.

Usage (when implemented)::

    python agents/evals/run_evals.py --agent critic --model <deployment> --smoke
"""

from __future__ import annotations


def load_fixtures(agent: str | None = None) -> list[dict]:
    raise NotImplementedError("Week 1-2: evaluation fixtures")


def run_suite(agent: str, model: str, smoke: bool = False) -> dict:
    """Return per-fixture scores plus aggregate, and persist the traces."""
    raise NotImplementedError("Week 9-10: agent research loop")
