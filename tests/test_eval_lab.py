"""Tests over the Evaluation Lab's own shape.

The lab is a corpus plus a rubric: data that defines correct behaviour, with no compiler to
catch its mistakes. So the invariants get asserted here, leaving the contents editable.

No model, no network, no credentials — these run in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "agents" / "evals"

RUBRIC = json.loads((EVALS / "rubric.json").read_text())
CONTROLS = json.loads((EVALS / "controls.json").read_text())
DIMS = {d["id"]: d for d in RUBRIC["dimensions"]}


# --- rubric -----------------------------------------------------------------

def test_rubric_covers_every_dimension_the_board_card_names():
    """The card's 'done when' names four: schema adherence, clarification quality,
    tool usage, criticism quality. All four must exist or the card is not satisfied."""
    for required in (
        "schema_adherence",
        "clarification_quality",
        "tool_usage",
        "criticism_quality",
    ):
        assert required in DIMS, f"board card names {required}; rubric omits it"


def test_every_dimension_declares_its_layer():
    """A dimension without a layer gets reported beside results that never tested it,
    which reads as proven. F-004."""
    for d in RUBRIC["dimensions"]:
        assert d["layer"] in {"deterministic", "model"}, d["id"]


def test_every_dimension_names_the_wrong_behaviour_too():
    """A dimension with only a pass condition is judged by vibes. Naming the failure
    makes it scorable."""
    for d in RUBRIC["dimensions"]:
        assert len(d["fail"]) > 20, f"{d['id']}: fail condition too thin to score against"


def test_critical_dimensions_must_pass_completely():
    assert RUBRIC["thresholds"]["critical"]["required_pass_rate"] == 1.0
    assert "block" in RUBRIC["thresholds"]["critical"]["on_regression"]


def test_the_refusal_for_the_right_reason_dimension_exists():
    """The whole reason the control set exists (F-001). If this dimension is ever
    deleted, an aggregate refusal count becomes reportable as safety evidence again."""
    d = DIMS["refusal_for_the_right_reason"]
    assert d["weight"] == "critical"
    assert "control" in d["scored_from"]


def test_model_layer_dimensions_are_not_claimed_as_deterministic():
    for name in ("tool_usage", "groundedness", "criticism_quality"):
        assert DIMS[name]["layer"] == "model"


# --- controls ---------------------------------------------------------------

def test_a_negative_control_exists():
    """Without a case expected to COMPILE cleanly, every rejection could be the
    baseline's own defect rather than the injected property."""
    base = [c for c in CONTROLS["controls"] if c["expected_verdict"] == "COMPILE"]
    assert base, "no control expects COMPILE — the harness cannot distinguish anything"


def test_controls_have_both_verdicts():
    """A harness where nothing can fail proves nothing."""
    verdicts = {c["expected_verdict"] for c in CONTROLS["controls"]}
    assert verdicts == {"COMPILE", "REJECT"}, verdicts


def test_every_control_isolates_one_named_property():
    for c in CONTROLS["controls"]:
        assert len(c["property_under_test"]) > 10, c["id"]
        assert c["expected_verdict"] in {"COMPILE", "REJECT"}


def test_reject_controls_say_what_must_not_happen():
    for c in CONTROLS["controls"]:
        assert len(c.get("must_not", "")) > 20, f"{c['id']} has no substantive must_not"


def test_the_hard_risk_limit_control_is_present_by_name():
    """C003 is the only case that isolates the 2% hard limit from the relational
    daily-limit check. Deleted in a refactor, F-002 becomes invisible again."""
    ids = {c["id"] for c in CONTROLS["controls"]}
    assert "C003-risk-3pct-generous-daily-limit" in ids
    c = next(c for c in CONTROLS["controls"] if c["id"].startswith("C003"))
    assert c["expected_verdict"] == "REJECT"
    assert c["mutation"]["risk.risk_per_trade_pct"] > 2


def test_layer_boundary_controls_expect_compile_and_say_why():
    """C005 (injection) and C006 (real money) deliberately COMPILE. A future editor
    'fixing' them would push content policy into a schema validator."""
    for cid in ("C005-prompt-injection-in-metadata", "C006-real-money-request"):
        c = next(c for c in CONTROLS["controls"] if c["id"] == cid)
        assert c["expected_verdict"] == "COMPILE"
        assert "layer_note" in c, f"{cid} must state which layer owns the property"


def test_baseline_is_the_blueprint_reference_spec():
    b = CONTROLS["baseline"]
    assert b["market"] == "BTC-PERP" and b["timeframe"] == "5m"
    assert b["exit"]["stop_loss_pct"] and b["exit"]["max_holding_minutes"]


# --- the harness actually runs ----------------------------------------------

def test_lab_runs_and_controls_discriminate():
    """Import and run the lab in-process. The point is has_discriminating_power:
    if every control returned the same verdict the numbers are meaningless."""
    import sys

    sys.path.insert(0, str(REPO))
    from agents.evals.run_lab import score_controls, score_ideas, score_unsafe

    controls = score_controls()
    assert controls["has_discriminating_power"], (
        "every control produced the same verdict — the harness cannot fail"
    )
    assert not controls["failures"], controls["failures"]

    ideas = score_ideas()
    assert not ideas["failures"], ideas["failures"]

    unsafe = score_unsafe()
    assert not unsafe["failures"], unsafe["failures"]


def test_underspecified_ideas_never_compile():
    """The Experiment 002 gate, asserted rather than eyeballed."""
    import sys

    sys.path.insert(0, str(REPO))
    from agents.evals.run_lab import score_ideas

    for row in score_ideas()["rows"]:
        if row["completeness"] in {"vague", "partial"}:
            assert row["verdict"] == "REJECT", f"{row['id']} compiled while under-specified"
            assert row["question_count"] > 0, f"{row['id']} asked nothing"


def test_run_record_names_what_it_did_not_measure():
    """dimensions_not_measured must never be empty at the deterministic layer — four
    rubric dimensions need a model. An empty list would imply full coverage."""
    import sys

    sys.path.insert(0, str(REPO))
    from agents.evals.run_lab import build_log, score_controls, score_ideas, score_unsafe

    log = build_log(score_ideas(), score_unsafe(), score_controls(), 0.0)
    assert log["dimensions_not_measured"], "a deterministic run cannot measure everything"
    assert log["layer"] == "deterministic"
    assert log["schema"] == "quantforge.eval-run/1"
    assert "no model was called" in log["honest_scope"]


def test_the_unsafe_corpus_caveat_survives():
    """F-001: this corpus refuses 13/13 for vagueness, not for danger. The caveat
    travels with the numbers or the false safety claim comes back."""
    import sys

    sys.path.insert(0, str(REPO))
    from agents.evals.run_lab import score_unsafe

    res = score_unsafe()
    assert "does not establish" in res["caveat"]
    assert res["reason_histogram"], "no reasons recorded — only a count would be reported"


# --- demo -------------------------------------------------------------------

def test_month1_demo_runs_clean():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(EVALS / "demo_month1.py")],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    # the demo must keep naming its seams, not just its successes
    assert "SEAM" in out, "stage 1 no longer labelled as manual"
    assert "NOT " in out, "the demo stopped listing what it does not prove"
    assert "PLACEHOLDER" in out, "the fee placeholder warning was dropped"


@pytest.mark.parametrize("doc", ["FAILURE_LOG.md", "RESULTS_LOG_FORMAT.md", "scoring.md"])
def test_prose_artifacts_exist(doc):
    assert (EVALS / doc).exists()


def test_failure_log_tracks_the_open_hard_limit_finding():
    """F-002 is an open contract question. If it is removed from the log it must be
    because it was fixed — and then C003 stops failing and this test's sibling catches it."""
    text = (EVALS / "FAILURE_LOG.md").read_text()
    assert "F-002" in text
    assert "F-001" in text and "vagueness" in text


def test_scoring_prose_and_rubric_json_agree():
    """Two copies of the rules diverge unless something checks. The JSON is what the
    harness consumes; the prose is what humans read in review."""
    prose = (EVALS / "scoring.md").read_text()
    for d in RUBRIC["dimensions"]:
        assert d["id"] in prose, f"{d['id']} is in rubric.json but not scoring.md"
