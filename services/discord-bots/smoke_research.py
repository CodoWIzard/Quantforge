"""End-to-end smoke test of the /research chain against the REAL backend.

Runs all five stages with actual model calls and prints each one. Does not touch
Discord: post() writes to stdout. Nothing is committed, traded or pushed.

This is the check that caught the truncation bug that the unit tests could not:
stage output is INPUT to the next stage, and only a real run shows what actually
travels. Run it after any change to the pipeline, the personas or ask_hermes.

    cd services/discord-bots && ../../.venv/bin/python smoke_research.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bots  # noqa: E402
import orchestrator  # noqa: E402

IDEA = ("buy BTC perps when price breaks the previous day's high on the 5 minute "
        "chart, cut it if it falls back below")


async def post(bot: str, label: str, text: str) -> None:
    print(f"\n{'=' * 70}\n### {label}   (posted as: {bot})\n{'=' * 70}")
    print(text)


async def main() -> int:
    t0 = time.monotonic()
    res = await orchestrator.run_pipeline(
        idea=IDEA, who="smoke-test", channel="playground",
        ask=bots.ask_hermes, personas=bots.PERSONAS, post=post,
    )
    print(f"\n{'=' * 70}")
    print(f"ok={res.ok}  stages={len(res.stages)}  failed_at={res.failed_at!r}")
    print(f"summary: {res.summary}")
    for r in res.stages:
        # A stage at exactly the old 1900-char cap is the truncation bug
        # returning; the length is printed so a regression is visible.
        print(f"  {r.stage.label}: {len(r.text)} chars in {r.seconds:.0f}s")
    print(f"wall clock: {(time.monotonic() - t0) / 60:.1f} min")
    return 0 if res.ok else 1


sys.exit(asyncio.run(main()))
