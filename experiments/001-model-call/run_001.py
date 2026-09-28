"""Experiment 001 — one model call returning structured output.

Exit gate: Reliable authentication, logging and cost visibility.

This script makes a single model call via the hermes CLI and asserts that:
  1. Authentication works (the call succeeds).
  2. The response is non-empty (we got output, not a silent failure).
  3. Token usage is visible from the CLI invocation (cost visibility).
  4. Timing is recorded (compute seconds gate from §50).

No network calls beyond the local hermes backend. No Azure. No trading logic.
The output is the evidence; the script does not fabricate numbers.

Run:
    .venv/bin/python experiments/001-model-call/run_001.py

Exit 0 = gate met. Exit 1 = gate not met, with the failure printed.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERMES = "hermes"

# -p is LOAD-BEARING. Without it the CLI inherits the host's sticky profile and
# prepends that profile's personal context: the first run of this script asked a
# prompt naming no instrument and got back "the MNQ1! futures trading assistant",
# plus an account size and unrelated bot projects. --ignore-user-config does NOT
# suppress it. See agents/evals/FAILURE_LOG.md F-005 and docs ADR-013.
PROFILE = os.environ.get("QUANTFORGE_HERMES_PROFILE", "quantforge")

# Written even when the run fails, so a pipeline can always account for spend.
USAGE_PATH = Path(tempfile.gettempdir()) / "quantforge_exp001_usage.json"

# Asked in the same call as the fixture prompt would be too clever - a model can
# answer one and ignore the other. This is a SEPARATE call whose whole job is to
# prove the backend will admit ignorance. A backend that cannot say this cannot
# be used to score groundedness.
CONTAMINATION_PROBE = (
    "Do not use any tools. Answer from context only, one line: name my primary "
    "trading instrument, my account size, and my name. If your context does not "
    "contain them, reply exactly UNKNOWN."
)

# Minimal structured prompt: ask the model to return a JSON object with known
# keys so we can assert the output parses and has the right shape.
PROMPT = """\
You are a test fixture for Experiment 001 of the QuantForge project.
Respond with ONLY a valid JSON object, no other text, matching this shape:
{
  "experiment": "001",
  "status": "ok",
  "message": "one sentence confirming the model call succeeded"
}
Do not add markdown fences. Output only the JSON object.
"""


def _read_usage() -> dict | None:
    """Load the usage report, or None if it was not written."""
    try:
        return json.loads(USAGE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _probe_contamination() -> str | None:
    """Ask the backend something the prompt does not answer. None = call failed.

    Deliberately a second process, not an extra line in the fixture prompt: a model
    asked two things can answer one and drop the other, and the drop would read as a
    clean result.
    """
    try:
        res = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            [HERMES, "-z", CONTAMINATION_PROBE,
             "-p", PROFILE,
             "--no-restore-cwd"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def run() -> int:
    print("Experiment 001 — model call with structured output")
    print("=" * 60)

    print(f"profile       : {PROFILE}")
    print(f"usage file    : {USAGE_PATH}")

    t0 = time.monotonic()
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            [HERMES, "-z", PROMPT,
             "-p", PROFILE,
             "--usage-file", str(USAGE_PATH),
             "--no-restore-cwd"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO),
        )
    except FileNotFoundError:
        print("FAIL: hermes CLI not found on PATH.")
        print("      Install hermes or check your PATH before running this experiment.")
        return 1
    except subprocess.TimeoutExpired:
        print("FAIL: hermes timed out after 120 seconds.")
        return 1

    elapsed = time.monotonic() - t0

    # Gate 1: process exited cleanly
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        print(f"FAIL: hermes exited {result.returncode}")
        if stderr:
            print("stderr:", stderr[:500])
        return 1

    # Gate 2: non-empty output
    if not stdout:
        print("FAIL: hermes returned empty output — authentication may have failed.")
        if stderr:
            print("stderr:", stderr[:500])
        return 1

    # Gate 3: output parses as valid JSON with expected keys
    # Strip a leading/trailing code fence if the model added one despite instructions.
    clean = stdout.strip("` \n")
    if clean.startswith("json"):
        clean = clean[4:].strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        print(f"FAIL: response is not valid JSON ({exc}).")
        print("Raw output (first 500 chars):", stdout[:500])
        return 1

    required_keys = {"experiment", "status", "message"}
    missing = required_keys - data.keys()
    if missing:
        print(f"FAIL: JSON response is missing keys: {missing}")
        print("Got:", data)
        return 1

    if data.get("status") != "ok":
        print(f"FAIL: status field is {data.get('status')!r}, expected 'ok'.")
        return 1

    print("\nAuthentication : OK (hermes responded)")
    print(f"Structured JSON: OK (keys: {sorted(data.keys())})")
    print(f"Model message  : {data.get('message', '')[:120]}")
    print(f"Compute seconds: {elapsed:.2f}s")

    # Gate 4: cost visibility from the usage file, not from a dashboard by hand.
    # Hand-copied numbers are how fabricated metrics enter a report.
    usage = _read_usage()
    if usage is None:
        print("FAIL: no usage file written — cost visibility is not demonstrated.")
        return 1
    if not usage.get("completed"):
        print(f"FAIL: usage reports the call did not complete: {usage}")
        return 1
    print(
        "Tokens         : "
        f"{usage.get('input_tokens')} in / {usage.get('output_tokens')} out / "
        f"{usage.get('cache_write_tokens')} cache-write / "
        f"{usage.get('total_tokens')} total"
    )
    print(
        f"Cost           : ${usage.get('estimated_cost_usd')} "
        f"({usage.get('api_calls')} call, {usage.get('model')} via "
        f"{usage.get('provider')})"
    )

    # Gate 5: the backend must be able to admit ignorance.
    # A clean call is not part of the gate's wording, but an unclean one makes the
    # result useless for the thing it exists to unblock (scoring groundedness),
    # so it is checked here rather than discovered downstream. F-005.
    print("\nContamination probe (F-005): asking for facts the prompt never gave...")
    leaked = _probe_contamination()
    if leaked is None:
        print("FAIL: probe call failed; cannot certify the backend is clean.")
        return 1
    if "UNKNOWN" not in leaked.upper():
        print("FAIL: backend volunteered context the prompt never supplied.")
        print(f"       reply: {leaked[:200]}")
        print(f"       profile {PROFILE!r} is not clean — see FAILURE_LOG F-005.")
        return 1
    print(f"  clean: backend replied {leaked[:60]!r}")

    print("\nGate: Reliable authentication, logging and cost visibility.")
    print("  Authentication : PASSED")
    print("  Logging        : PASSED (output above is the log)")
    print("  Cost visibility: PASSED (tokens + cost from --usage-file)")
    print("  Backend clean  : PASSED (F-005 probe)")
    print("\nExperiment 001 exit gate: MET.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
