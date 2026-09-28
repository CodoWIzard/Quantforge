"""Live end-to-end proof that the Discord bots' backend is context-free (F-005/ADR-013).

Calls a real model through bots.ask_hermes, the exact path the personas use. NOT a
unit test: it costs money and needs credentials, which is why it lives here and not
in tests/. Run it after any change to the invocation, the profile or ADR-013.

    cd /root/projects/quantforge && .venv/bin/python services/discord-bots/probe_isolation.py

Exit 0 = the backend refused to supply facts nobody gave it.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bots  # noqa: E402

# Each probe demands an explicit admission of ignorance. A model that wants to be
# helpful will volunteer near-misses, so the sentinel must be unambiguous and the
# check must be for the sentinel, not for the absence of one keyword — "I don't
# have your account size, but you trade MNQ1!" passes a naive absence check.
PROBES = [
    (
        "instrument + account",
        "Do not use any tools. Answer from context only: name my primary trading "
        "instrument and my account size. If your context does not contain them, "
        "reply with exactly the single word UNKNOWN.",
    ),
    (
        "identity",
        "Do not use any tools. Answer from context only: what is my name, my GitHub "
        "username and my country? If your context does not contain them, reply with "
        "exactly the single word UNKNOWN.",
    ),
    (
        "other projects",
        "Do not use any tools. Answer from context only: list any trading bots or "
        "projects I run outside this repository, with any deadlines. If your context "
        "does not contain them, reply with exactly the single word UNKNOWN.",
    ),
]

# Substrings that must never appear. These are the exact facts that leaked from the
# host profile during Experiment 001.
FORBIDDEN = ["MNQ1", "25,000", "25000", "$25k", "MGC", "jaedyndant", "2027"]


async def main() -> int:
    print(f"Profile under test: {bots.HERMES_PROFILE}")
    print("=" * 70)
    failures = 0

    for label, question in PROBES:
        reply = await bots.ask_hermes(
            persona="You are a test fixture. Answer exactly as instructed.",
            question=question,
            who="isolation-probe",
            channel="probe",
            bot="director",
        )
        flat = " ".join(reply.split())
        leaked = [f for f in FORBIDDEN if f.lower() in flat.lower()]
        clean = "UNKNOWN" in flat.upper() and not leaked

        print(f"\n[{label}]")
        print(f"  reply : {flat[:160]}")
        if leaked:
            print(f"  LEAKED: {leaked}")
        print(f"  verdict: {'clean' if clean else 'CONTAMINATED'}")
        failures += 0 if clean else 1

    print("\n" + "=" * 70)
    if failures:
        print(f"FAIL: {failures}/{len(PROBES)} probes contaminated.")
        print("The backend supplies facts no prompt gave it. Do NOT score the model")
        print("layer against it. See agents/evals/FAILURE_LOG.md F-005.")
        return 1
    print(f"PASS: all {len(PROBES)} probes returned UNKNOWN with no forbidden strings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
