"""QuantForge Evaluation Lab — deterministic scoring layer.

Week 4 board card: *"The team can run an evaluation set and score whether changes
improve schema adherence, clarification quality, tool usage and criticism quality."*

This module is the DETERMINISTIC half. It drives the real compiler over the committed
corpora and the isolation controls. No model, no network, no credentials — so it runs in
CI and for the next agent, which is the point.

    .venv/bin/python agents/evals/run_lab.py
    .venv/bin/python agents/evals/run_lab.py --json runs/          # also write a results log

Exit 0 = every critical assertion held. Non-zero = listed failures by fixture id.

WHAT THIS CANNOT SCORE
----------------------
tool_usage, groundedness, criticism_quality and self_review_disclosure are model-layer
dimensions. Nothing here exercises them. They require the model-backed pass
(services/discord-bots/smoke_research.py) and are reported as NOT MEASURED rather than
silently omitted — a dimension missing from a report reads as a dimension that passed.
"""

from __future__ import annotations

import argparse
import copy
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from packages.strategy_schema.compiler import (  # noqa: E402
    clarification_questions,
    compile_candidate,
)
from packages.strategy_schema.errors import StrategyCompileError  # noqa: E402

EVALS = REPO / "agents" / "evals"
EXP002 = REPO / "experiments" / "002-strategy-compiler"

RUBRIC = json.loads((EVALS / "rubric.json").read_text())
CONTROLS = json.loads((EVALS / "controls.json").read_text())

MODEL_LAYER_DIMENSIONS = [
    d["id"] for d in RUBRIC["dimensions"] if d["layer"] == "model"
]


# ---------------------------------------------------------------------------
# verdict primitive — one place that decides what the compiler said
# ---------------------------------------------------------------------------

def verdict_of(candidate: dict) -> dict:
    """Run the compiler and return a structured verdict.

    Always reports the REASON, never a bare pass/fail. Identical reasons across
    categories that ought to differ is the tell that a check has no discriminating
    power (rubric: refusal_for_the_right_reason).
    """
    questions = clarification_questions(candidate)
    try:
        spec = compile_candidate(candidate)
    except StrategyCompileError as exc:
        return {
            "verdict": "REJECT",
            "error_type": type(exc).__name__,
            "reason": str(exc),
            "question_count": len(questions),
            "questions": questions,
        }
    return {
        "verdict": "COMPILE",
        "error_type": None,
        "reason": "compiled",
        "question_count": len(questions),
        "questions": questions,
        "spec_hash": spec.canonical_hash(),
    }


def _apply(mutation: dict, base: dict) -> dict:
    """Apply a control's dotted-path mutation to a deep copy of the baseline.

    Two forms: ``a.b`` sets a value, ``a.b.append`` appends to a list. Anything else
    raises rather than silently no-opping — a typo'd control path would otherwise
    produce a control that tests the untouched baseline and quietly passes.
    """
    cand = copy.deepcopy(base)
    for path, value in mutation.items():
        if path.endswith(".append"):
            node: object = cand
            for part in path[: -len(".append")].split("."):
                if not isinstance(node, dict):
                    raise TypeError(f"control path {path!r}: {part!r} is not a mapping")
                node = node[part]
            if not isinstance(node, list):
                raise TypeError(f"control path {path!r} does not resolve to a list")
            node.append(value)
            continue
        parts = path.split(".")
        target = cand
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return cand


# ---------------------------------------------------------------------------
# dimension: clarification_quality + no_invented_parameter (B2 idea corpus)
# ---------------------------------------------------------------------------

def score_ideas() -> dict:
    """Drive the B2 idea corpus.

    LAYER BOUNDARY — read before adding assertions here. The corpus stores raw human
    sentences; the compiler consumes a structured candidate. Feeding `{"raw_input": ...}`
    means every structural trigger (timeframe, direction, market, execute_at) sees an
    absent field and fires, regardless of what the sentence actually said.

    So the two directions are NOT symmetrically testable at this layer:

      under-specified -> must ask, must not compile   TESTABLE, and the real gate
      complete        -> must ask nothing             NOT TESTABLE from prose

    A complete sentence like I015 produces 11 questions here, and that is the missing
    sentence->structure parser, not a clarification-rule defect. Scoring it as a compiler
    failure would send the next person to fix the rules, which are correct. The
    not-listening direction is tested instead by control C008, which supplies the SAME
    strategy already structured and requires zero questions.
    """
    failures: list[dict] = []
    not_measurable: list[dict] = []
    rows: list[dict] = []

    for path in sorted((EXP002 / "ideas").glob("*.json")):
        doc = json.loads(path.read_text())
        res = verdict_of({"raw_input": doc["raw_input"]})
        underspecified = doc["completeness"] in {"vague", "partial"}
        row = {
            "id": doc["id"],
            "completeness": doc["completeness"],
            "declared_missing": doc["missing_fields"],
            **res,
        }
        rows.append(row)

        if underspecified:
            if res["question_count"] == 0:
                failures.append({
                    "id": doc["id"],
                    "dimension": "clarification_quality",
                    "detail": (
                        f"asked NOTHING for an under-specified idea; declared missing: "
                        f"{', '.join(doc['missing_fields'])}"
                    ),
                })
            if res["verdict"] == "COMPILE":
                failures.append({
                    "id": doc["id"],
                    "dimension": "no_invented_parameter",
                    "detail": (
                        f"compiled with {res['question_count']} unanswered question(s) — "
                        "a silent invented default"
                    ),
                })
        elif res["question_count"] > 0:
            not_measurable.append({
                "id": doc["id"],
                "dimension": "clarification_quality",
                "detail": (
                    f"{doc['completeness']} idea drew {res['question_count']} questions, "
                    "but it was supplied as prose and no parser turned it into fields — "
                    "this measures the missing parser, not the rules. See control C008."
                ),
            })

    return {"rows": rows, "failures": failures, "not_measurable": not_measurable}


# ---------------------------------------------------------------------------
# dimension: schema_adherence (V2 unsafe corpus) — reported WITH its caveat
# ---------------------------------------------------------------------------

def score_unsafe() -> dict:
    """Run the REJECT-class unsafe corpus and record WHY each refused.

    Deliberately does NOT conclude that unsafe input is refused. Every V2 request is raw
    prose and therefore under-specified, so a refusal here is explained by vagueness. The
    controls, not this function, carry the safety evidence.
    """
    rows: list[dict] = []
    failures: list[dict] = []
    reasons: dict[str, int] = {}

    for path in sorted((EXP002 / "unsafe").glob("*.json")):
        doc = json.loads(path.read_text())
        if doc["expected_response"] != "REJECT":
            continue
        res = verdict_of({"raw_input": doc["request"]})
        rows.append({"id": doc["id"], "category": doc["category"], **res})
        if res["verdict"] == "COMPILE":
            failures.append({
                "id": doc["id"],
                "dimension": "schema_adherence",
                "detail": f"compiled without objection; expected REJECT because {doc['why']}",
            })
        else:
            key = res["error_type"]
            reasons[key] = reasons.get(key, 0) + 1

    # discriminating-power check: if every refusal has the same reason, say so
    monoculture = len(reasons) == 1 and rows
    return {
        "rows": rows,
        "failures": failures,
        "reason_histogram": reasons,
        "single_reason_for_every_refusal": bool(monoculture),
        "caveat": (
            "Every fixture in this corpus is raw prose, hence under-specified. A refusal "
            "here does not establish that the unsafe CONTENT was detected. See controls."
        ),
    }


# ---------------------------------------------------------------------------
# dimension: refusal_for_the_right_reason (isolation controls)
# ---------------------------------------------------------------------------

def score_controls() -> dict:
    base = {k: v for k, v in CONTROLS["baseline"].items() if not k.startswith("_")}
    rows: list[dict] = []
    failures: list[dict] = []
    known_gaps: list[dict] = []
    verdicts_seen: set[str] = set()

    for ctl in CONTROLS["controls"]:
        cand = _apply(ctl.get("mutation", {}), base)
        res = verdict_of(cand)
        verdicts_seen.add(res["verdict"])
        ok = res["verdict"] == ctl["expected_verdict"]

        if ok and ctl.get("expected_error"):
            ok = res["error_type"] == ctl["expected_error"]
        # Mechanism check. An exception CLASS is not a mechanism: two different rules
        # both raise ImpossibleRiskError, so C002 kept passing after the hard-limit
        # ceiling was removed because its relational rule caught the same input. A
        # control that cannot name the rule that fired cannot detect that the rule it
        # claims to test is gone (F-002).
        if ok and ctl.get("expected_reason_contains"):
            ok = ctl["expected_reason_contains"].lower() in res["reason"].lower()
        if ok and "expected_question_count" in ctl:
            ok = res["question_count"] == ctl["expected_question_count"]

        rows.append({
            "id": ctl["id"],
            "property": ctl["property_under_test"],
            "expected": ctl["expected_verdict"],
            "expected_error": ctl.get("expected_error"),
            "expected_reason_contains": ctl.get("expected_reason_contains"),
            "passed": ok,
            **res,
        })

        if not ok:
            want = ctl["expected_verdict"]
            if ctl.get("expected_error"):
                want += "/" + ctl["expected_error"]
            if ctl.get("expected_reason_contains"):
                want += "/reason~" + ctl["expected_reason_contains"]
            entry = {
                "id": ctl["id"],
                "dimension": "refusal_for_the_right_reason",
                "detail": (
                    f"expected {want}, got {res['verdict']}/{res['error_type']}"
                    f" — {res['reason'][:120]}"
                ),
            }
            # controls flagged as currently_failing are tracked, not merge-blocking:
            # they are open findings in FAILURE_LOG.md, already reported to the team.
            (known_gaps if ctl.get("currently_failing") else failures).append(entry)

    return {
        "rows": rows,
        "failures": failures,
        "known_gaps": known_gaps,
        "has_discriminating_power": len(verdicts_seen) > 1,
    }


# ---------------------------------------------------------------------------
# results log
# ---------------------------------------------------------------------------

def _git(*args: str) -> str:
    """Read git provenance, or report it as unavailable.

    Never raises: a run whose commit cannot be read is still a valid run, it is just
    less comparable — and returning "unavailable" says so in the record rather than
    aborting the evaluation. Fixed argv, no shell, no user input.
    """
    git = shutil.which("git")
    if git is None:
        return "unavailable"
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            [git, *args], cwd=REPO, capture_output=True, text=True, timeout=10, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def build_log(ideas: dict, unsafe: dict, controls: dict, elapsed: float) -> dict:
    """The results-log record. One JSON object per run, appended to a run directory.

    Every field is something a later reader needs to decide whether two runs are
    comparable: without the commit and the rubric version, a score delta between runs
    is uninterpretable.
    """
    critical = ideas["failures"] + unsafe["failures"] + controls["failures"]
    return {
        "schema": "quantforge.eval-run/1",
        "run_id": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "layer": "deterministic",
        "target": "packages/strategy_schema",
        "provenance": {
            "commit": _git("rev-parse", "--short", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_git("status", "--porcelain")),
            "rubric_version": RUBRIC["rubric_version"],
            "control_set_version": CONTROLS["control_set_version"],
            "python": platform.python_version(),
        },
        "counts": {
            "ideas": len(ideas["rows"]),
            "unsafe_reject_cases": len(unsafe["rows"]),
            "controls": len(controls["rows"]),
        },
        "dimensions_measured": [
            d["id"] for d in RUBRIC["dimensions"] if d["layer"] == "deterministic"
        ],
        "dimensions_not_measured": MODEL_LAYER_DIMENSIONS,
        "results": {
            "controls_passed": sum(1 for r in controls["rows"] if r["passed"]),
            "controls_total": len(controls["rows"]),
            "has_discriminating_power": controls["has_discriminating_power"],
            "unsafe_reason_histogram": unsafe["reason_histogram"],
            "single_reason_for_every_refusal": unsafe["single_reason_for_every_refusal"],
        },
        "critical_failures": critical,
        "known_gaps": controls["known_gaps"],
        "not_measurable": ideas["not_measurable"],
        "verdict": "PASS" if not critical else "FAIL",
        "elapsed_s": round(elapsed, 3),
        "honest_scope": (
            "Deterministic layer only. No natural language was parsed and no model was "
            "called: sentence -> structured candidate is the agent's job and is not "
            "exercised here. Model-layer dimensions are NOT MEASURED."
        ),
    }


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", metavar="DIR", help="append the run record to DIR/runs.jsonl")
    args = ap.parse_args()

    t0 = time.monotonic()
    ideas = score_ideas()
    unsafe = score_unsafe()
    controls = score_controls()
    log = build_log(ideas, unsafe, controls, time.monotonic() - t0)

    print("QuantForge Evaluation Lab — deterministic layer")
    print("=" * 74)
    print(f"target   : {log['target']}")
    print(f"commit   : {log['provenance']['commit']}"
          f"{' (dirty)' if log['provenance']['dirty'] else ''}")
    print(f"rubric   : v{log['provenance']['rubric_version']}"
          f"   controls v{log['provenance']['control_set_version']}")  # noqa: E501

    print("\nB2 idea corpus — clarification_quality, no_invented_parameter")
    asked = sum(1 for r in ideas["rows"] if r["question_count"])
    print(f"  ideas                   : {len(ideas['rows'])}")
    print(f"  produced questions      : {asked}")
    compiled = sum(1 for r in ideas["rows"] if r["verdict"] == "COMPILE")
    print(f"  compiled                : {compiled}")

    print("\nV2 unsafe corpus (REJECT class) — reasons, not a score")
    for err, n in sorted(unsafe["reason_histogram"].items()):
        print(f"  {err:26}: {n}")
    if unsafe["single_reason_for_every_refusal"]:
        print("  !! every refusal has the SAME reason — this corpus is not")
        print("     discriminating for unsafe CONTENT. See the controls below.")

    print("\nIsolation controls — refusal_for_the_right_reason")
    for r in controls["rows"]:
        mark = "ok  " if r["passed"] else "FAIL"
        got = r["error_type"] or "compiled"
        print(f"  [{mark}] {r['id']:38} exp={r['expected']:8} got={r['verdict']:8} {got}")
    if not controls["has_discriminating_power"]:
        print("  !! every control returned the same verdict — the harness cannot fail,")
        print("     so it proves nothing. Fix before trusting any result above.")

    if ideas["not_measurable"]:
        print(f"\n  NOT MEASURABLE at this layer ({len(ideas['not_measurable'])} ideas):")
        print("    complete/edge ideas are stored as prose and no sentence->structure")
        print("    parser exists, so their question count reflects the missing parser.")
        print("    The not-listening property is tested by control C008 instead.")
        print("    ids: " + ", ".join(e["id"] for e in ideas["not_measurable"]))

    print("\nNOT MEASURED (model layer, needs smoke_research.py):")
    for d in MODEL_LAYER_DIMENSIONS:
        print(f"  - {d}")

    if controls["known_gaps"]:
        n_gaps = len(controls["known_gaps"])
        print(f"\nKNOWN GAPS ({n_gaps}) — in FAILURE_LOG.md, not blocking:")
        for g in controls["known_gaps"]:
            print(f"  - {g['id']}: {g['detail']}")

    if log["critical_failures"]:
        print(f"\nCRITICAL FAILURES ({len(log['critical_failures'])}):")
        for f in log["critical_failures"]:
            print(f"  - [{f['dimension']}] {f['id']}: {f['detail']}")

    if args.json:
        out = Path(args.json)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "runs.jsonl").open("a") as fh:
            fh.write(json.dumps(log) + "\n")
        print(f"\nrun record appended to {out / 'runs.jsonl'}")

    print(f"\nverdict: {log['verdict']}  ({log['elapsed_s']}s)")
    return 0 if log["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
