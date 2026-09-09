"""Experiment 002 — strategy compiler: messy idea -> schema-valid StrategySpec.

Exit gate: 10-20 test prompts produce no silent invented parameters.

This drives compile_candidate() and clarification_questions() from
packages/strategy_schema/ over the committed B2 idea corpus (I001-I020)
and the V2 unsafe corpus (U001-U018).

It is DETERMINISTIC: no model, no network, no Azure. Every number it prints
comes from executing the code in this repo. Per AGENTS.md: AI never computes
authoritative metrics — Python does.

Run:
    .venv/bin/python experiments/002-strategy-compiler/run_002.py

Exit 0 = gate met (10-20 prompts, zero silent inventions).
Exit 1 = gate not met, with failures listed.

The gate is: "10-20 test prompts produce no silent invented parameters."
This run uses the 20 B2 ideas as the prompt corpus and checks that every
under-specified idea produces clarification questions and refuses to compile,
never silently inventing a missing value.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from packages.strategy_schema.compiler import (  # noqa: E402
    clarification_questions,
    compile_candidate,
)
from packages.strategy_schema.errors import StrategyCompileError  # noqa: E402

EXP = REPO / "experiments" / "002-strategy-compiler"


def _candidate_from_idea(doc: dict) -> dict:
    """Feed the compiler exactly what the idea fixture declares as raw input."""
    return {"raw_input": doc["raw_input"]}


def check_idea_corpus() -> tuple[list[str], dict]:
    """
    Under-specified ideas (vague/partial) must produce questions, not compiled specs.
    Complete/edge ideas should compile without error.

    Gate invariant: NO silent invented parameter.
    Silence = compile_candidate() returns a StrategySpec while clarification_questions()
    was non-empty for the same input.
    """
    failures: list[str] = []
    stats: dict = {
        "total": 0,
        "vague": 0,
        "partial": 0,
        "complete": 0,
        "edge": 0,
        "correctly_questioned": 0,
        "correctly_refused": 0,
        "silent_inventions": 0,
        "total_questions_generated": 0,
    }

    idea_files = sorted((EXP / "ideas").glob("*.json"))
    stats["total"] = len(idea_files)

    for path in idea_files:
        doc = json.loads(path.read_text())
        completeness = doc["completeness"]
        stats[completeness] = stats.get(completeness, 0) + 1

        candidate = _candidate_from_idea(doc)
        questions = clarification_questions(candidate)
        stats["total_questions_generated"] += len(questions)

        if completeness in ("vague", "partial"):
            if not questions:
                stats["silent_inventions"] += 1
                failures.append(
                    f"{doc['id']} [{completeness}]: clarification_questions() returned "
                    f"NOTHING — compiler either invented values or missed the gap. "
                    f"Missing fields declared in fixture: {', '.join(doc['missing_fields'])}"
                )
                continue

            stats["correctly_questioned"] += 1

            # The critical check: must refuse to compile, not silently invent defaults.
            try:
                compile_candidate(candidate)
                stats["silent_inventions"] += 1
                failures.append(
                    f"{doc['id']} [{completeness}]: compile_candidate() SUCCEEDED "
                    f"despite {len(questions)} unanswered question(s). "
                    f"This is a silent invented-default — the exact failure the gate exists "
                    f"to catch. First question: {questions[0][:120]}"
                )
            except StrategyCompileError:
                stats["correctly_refused"] += 1  # correct: asked, then refused

        # complete/edge: we note whether they compile but do not assert it here,
        # because the full pydantic model may need fields the minimal fixture omits.
        # The gate is specifically about the no-silent-invention property.

    return failures, stats


def check_unsafe_corpus() -> tuple[list[str], dict]:
    """
    Impossible/unsafe requests marked REJECT must never compile silently.
    CLARIFY and COMPILE_WITH_WARNING cases are not checked here (they are V3 scope).
    """
    failures: list[str] = []
    stats: dict = {
        "total": 0,
        "reject_cases": 0,
        "correctly_refused": 0,
        "silent_compilations": 0,
    }

    unsafe_files = sorted((EXP / "unsafe").glob("*.json"))
    stats["total"] = len(unsafe_files)

    for path in unsafe_files:
        doc = json.loads(path.read_text())
        if doc["expected_response"] != "REJECT":
            continue

        stats["reject_cases"] += 1
        candidate = {"raw_input": doc["request"]}

        try:
            compile_candidate(candidate)
            stats["silent_compilations"] += 1
            failures.append(
                f"{doc['id']} [{doc['category']}]: compiled without objection. "
                f"Expected REJECT. Reason per fixture: {doc['why']}"
            )
        except StrategyCompileError:
            stats["correctly_refused"] += 1

    return failures, stats


def main() -> int:
    t0 = time.monotonic()

    print("Experiment 002 — strategy compiler gate check")
    print("=" * 60)
    print("Exit gate: 10-20 test prompts produce no silent invented parameters.")
    print()

    idea_failures, idea_stats = check_idea_corpus()
    unsafe_failures, unsafe_stats = check_unsafe_corpus()

    elapsed = time.monotonic() - t0

    print(f"B2 idea corpus ({idea_stats['total']} prompts)")
    print(f"  vague      : {idea_stats['vague']}")
    print(f"  partial    : {idea_stats['partial']}")
    print(f"  complete   : {idea_stats['complete']}")
    print(f"  edge       : {idea_stats['edge']}")
    print(f"  correctly questioned : {idea_stats['correctly_questioned']}")
    print(f"  correctly refused    : {idea_stats['correctly_refused']}")
    print(f"  silent inventions    : {idea_stats['silent_inventions']}  <- must be 0")
    print(f"  questions generated  : {idea_stats['total_questions_generated']}")
    print()
    print(f"V2 unsafe corpus ({unsafe_stats['total']} prompts, "
          f"{unsafe_stats['reject_cases']} REJECT cases)")
    print(f"  correctly refused    : {unsafe_stats['correctly_refused']}")
    print(f"  silent compilations  : {unsafe_stats['silent_compilations']}  <- must be 0")
    print()
    print(f"Compute seconds: {elapsed:.3f}s")

    all_failures = idea_failures + unsafe_failures

    # Gate check: the corpus size must be in the 10-20 range the gate specifies.
    corpus_size = idea_stats["total"]
    if not (10 <= corpus_size <= 20):
        all_failures.append(
            f"Corpus size {corpus_size} is outside the gate's 10-20 range. "
            "Add or remove idea fixtures so the corpus is within bounds."
        )

    if all_failures:
        print(f"FAILURES ({len(all_failures)}):")
        for f in all_failures:
            print(f"  - {f}")
        print()
        print("Experiment 002 gate: NOT MET.")
        return 1

    print("All checks passed:")
    print("  - Zero silent invented parameters across the idea corpus.")
    print("  - All REJECT-class unsafe requests refused to compile.")
    print(f"  - Corpus size {corpus_size} is within the 10-20 gate range.")
    print()
    print("Experiment 002 gate: MET.")
    print("  Record this output in experiments/002-strategy-compiler/RESULT.md")
    print("  to close the gate per AGENTS.md definition of done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
