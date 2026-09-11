"""End-to-end smoke test of the /research chain against the REAL backend.

Runs every stage with actual model calls and prints each one. Does not touch
Discord: post() writes to stdout. Nothing is committed, traded or pushed.

This is the check that caught the truncation bug that the unit tests could not:
stage output is INPUT to the next stage, and only a real run shows what actually
travels. Run it after any change to the pipeline, the personas or ask_hermes.

    cd services/discord-bots && ../../.venv/bin/python smoke_research.py
    ../../.venv/bin/python smoke_research.py "my own idea here"

Beyond ok/failed it reports the three things a live run can show and a unit test
cannot, all of them ADR-011 properties (one Director in several modes):

  identities  - which bot actually published each stage. After ADR-011 every
                stage is the director; a specialist name appearing here means
                the pipeline was rewired without the ADR being updated.
  self-review - the critic stage must admit it wrote the spec, and the verdict
                must tell the user all stages were one agent. Both are the only
                thing standing in for the independent reviewer ADR-011 removed,
                and a model silently dropping a disclosure is invisible in a
                transcript that otherwise looks complete.
  echoed      - a stage opening with the ----- context delimiter, i.e. copying
                the transcript's framing into its own answer.

These are reported, not asserted: this script talks to a live model, so a miss
is a signal to read the stage, not a build failure. Exit status still tracks
res.ok alone.
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

# Substrings that show a stage owned up to marking its own homework. Matching is
# loose on purpose - the phrasing is the model's, only the admission is required.
SELF_REVIEW_MARKERS = ("i wrote the spec", "i wrote this spec", "my own work",
                       "own homework", "all four stages were me", "every stage was me",
                       "same agent", "no independent", "not independently",
                       "self-review", "a mirror")

posted: list[tuple[str, str, str]] = []


async def post(bot: str, label: str, text: str) -> None:
    posted.append((bot, label, text))
    print(f"\n{'=' * 70}\n### {label}   (posted as: {bot})\n{'=' * 70}")
    print(text)


async def main() -> int:
    idea = " ".join(sys.argv[1:]).strip() or IDEA
    print(f"idea: {idea}\n")
    t0 = time.monotonic()
    res = await orchestrator.run_pipeline(
        idea=idea, who="smoke-test", channel="playground",
        ask=bots.ask_hermes, personas=bots.PERSONAS, post=post,
    )
    print(f"\n{'=' * 70}")
    print(f"ok={res.ok}  stages={len(res.stages)}  failed_at={res.failed_at!r}")
    print(f"summary: {res.summary}")
    for r in res.stages:
        # A stage at exactly the old 1900-char cap is the truncation bug
        # returning; the length is printed so a regression is visible.
        low = r.text.lower()
        flags = []
        if any(m in low for m in SELF_REVIEW_MARKERS):
            flags.append("self-review disclosed")
        if r.text.lstrip().startswith("-----"):
            flags.append("ECHOED DELIMITER")
        suffix = f"   [{', '.join(flags)}]" if flags else ""
        print(f"  {r.stage.label}: {len(r.text)} chars in {r.seconds:.0f}s{suffix}")

    print(f"identities: {[b for b, _, _ in posted]}")
    disclosed = sum(
        any(m in r.text.lower() for m in SELF_REVIEW_MARKERS) for r in res.stages
    )
    if res.ok and disclosed < 2:
        # Expected in the critic stage AND the verdict. Fewer means the run reads
        # like several independent reviewers, which is exactly what it is not.
        print("WARNING: self-review disclosed in only "
              f"{disclosed} stage(s) - expected the critic and the verdict.")
    print(f"wall clock: {(time.monotonic() - t0) / 60:.1f} min")
    return 0 if res.ok else 1


sys.exit(asyncio.run(main()))
