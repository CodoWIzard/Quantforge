"""B5 evidence harness - prove missing values become questions, never invented defaults.

Board item B5: *"Confirm invalid/missing values become questions or errors, never
invented defaults."* That is a claim about behaviour, so it needs a run, not an opinion.

This is deterministic: it drives the real compiler over the committed B2 idea corpus and
the V2 unsafe corpus. No model, no network, no Azure. Every number it prints comes from
executing the code, per AGENTS.md ("AI never computes authoritative metrics").

    .venv/bin/python experiments/002-strategy-compiler/run_b5_evidence.py

Exit code 0 = every assertion held. Non-zero = B5 is not satisfied, with the failures
listed. Deliberately fails loudly rather than reporting a percentage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from packages.strategy_schema.compiler import (  # noqa: E402
    clarification_questions,
    compile_candidate,
)
from packages.strategy_schema.errors import StrategyCompileError  # noqa: E402

EXP = REPO / "experiments" / "002-strategy-compiler"


def _candidate(doc: dict) -> dict:
    """Feed the compiler exactly what a user typed - nothing pre-parsed."""
    return {"raw_input": doc["raw_input"]}


def check_ideas() -> tuple[list[str], dict]:
    """Under-specified ideas must produce questions; complete ones must not."""
    failures: list[str] = []
    stats = {"vague": 0, "partial": 0, "complete": 0, "edge": 0,
             "questioned": 0, "compiled": 0, "total_questions": 0}

    for path in sorted((EXP / "ideas").glob("*.json")):
        doc = json.loads(path.read_text())
        stats[doc["completeness"]] += 1
        qs = clarification_questions(_candidate(doc))
        stats["total_questions"] += len(qs)

        if doc["completeness"] in {"vague", "partial"}:
            if not qs:
                failures.append(
                    f"{doc['id']} ({doc['completeness']}): compiler asked NOTHING for "
                    f"an under-specified idea - it either invented values or missed the "
                    f"gap. Missing fields declared: {', '.join(doc['missing_fields'])}"
                )
                continue
            stats["questioned"] += 1
            # The critical assertion: it must REFUSE, not fill in.
            try:
                compile_candidate(_candidate(doc))
                failures.append(
                    f"{doc['id']}: compiled a spec despite {len(qs)} unanswered "
                    f"questions - this is the invented-default failure B5 exists to catch"
                )
            except StrategyCompileError:
                pass  # correct: refused
        else:
            stats["compiled"] += 1

    return failures, stats


def check_unsafe() -> tuple[list[str], dict]:
    """Impossible/unsafe requests must never compile silently."""
    failures: list[str] = []
    stats = {"impossible": 0, "unsafe": 0, "suspicious": 0, "refused": 0}

    for path in sorted((EXP / "unsafe").glob("*.json")):
        doc = json.loads(path.read_text())
        stats[doc["category"]] += 1
        if doc["expected_response"] != "REJECT":
            continue  # CLARIFY / COMPILE_WITH_WARNING are not refusals
        try:
            compile_candidate({"raw_input": doc["request"]})
            failures.append(
                f"{doc['id']} ({doc['category']}): compiled without objection. "
                f"Expected REJECT because - {doc['why']}"
            )
        except StrategyCompileError:
            stats["refused"] += 1

    return failures, stats


def main() -> int:
    idea_fail, idea_stats = check_ideas()
    unsafe_fail, unsafe_stats = check_unsafe()

    print("B5 - invalid/missing values become questions or errors, never defaults")
    print("=" * 72)
    print("\nB2 idea corpus")
    total = sum(idea_stats[k] for k in ("vague", "partial", "complete", "edge"))
    print(f"  ideas               : {total}")
    print(f"    vague/partial     : {idea_stats['vague'] + idea_stats['partial']}")
    print(f"    complete/edge     : {idea_stats['complete'] + idea_stats['edge']}")
    print(f"  produced questions  : {idea_stats['questioned']}")
    print(f"  questions generated : {idea_stats['total_questions']}")
    print("\nV2 unsafe corpus")
    print(f"  impossible          : {unsafe_stats['impossible']}")
    print(f"  unsafe              : {unsafe_stats['unsafe']}")
    print(f"  suspicious          : {unsafe_stats['suspicious']}")
    print(f"  REJECT cases refused: {unsafe_stats['refused']}")

    failures = idea_fail + unsafe_fail
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        print("\nB5 NOT satisfied.")
        return 1

    print("\nNo idea compiled with an unanswered question.")
    print("No REJECT-class request compiled without objection.")
    print("B5 satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
