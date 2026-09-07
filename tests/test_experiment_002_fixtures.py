"""B2 / B4 / V2 fixtures are the Experiment 002 exit gate - assert they stay usable.

The gate is *"10-20 test prompts produce no silent invented parameters"*. These tests do
not run a model; they lock the fixture corpus itself so it cannot silently rot, lose its
adversarial cases, or drift out of the schema's scope.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXP = Path(__file__).resolve().parent.parent / "experiments" / "002-strategy-compiler"
IDEAS = sorted((EXP / "ideas").glob("*.json"))
UNSAFE = sorted((EXP / "unsafe").glob("*.json"))


def _load(paths):
    return [json.loads(p.read_text()) for p in paths]


# ---------------------------------------------------------------- B2: ideas

def test_idea_count_meets_the_gate():
    """The exit gate names 10-20 prompts."""
    assert 10 <= len(IDEAS) <= 20, f"found {len(IDEAS)}"


@pytest.mark.parametrize("path", IDEAS, ids=lambda p: p.stem)
def test_idea_is_wellformed(path: Path):
    doc = json.loads(path.read_text())
    for key in ("id", "completeness", "raw_input", "missing_fields",
                "expected_behaviour", "must_not"):
        assert key in doc, f"{path.name} missing {key}"
    assert doc["completeness"] in {"vague", "partial", "complete", "edge"}


def test_corpus_is_weighted_toward_underspecified_input():
    """Real users arrive vague. A corpus of clean specs would not exercise the compiler."""
    docs = _load(IDEAS)
    incomplete = [d for d in docs if d["completeness"] in {"vague", "partial"}]
    assert len(incomplete) >= len(docs) * 0.6


def test_complete_ideas_have_no_missing_fields():
    """A 'complete' idea that still needs questions is mislabelled."""
    for d in _load(IDEAS):
        if d["completeness"] == "complete":
            assert d["missing_fields"] == [], f"{d['id']} is not actually complete"


def test_incomplete_ideas_declare_what_is_missing():
    for d in _load(IDEAS):
        if d["completeness"] in {"vague", "partial"}:
            assert d["missing_fields"], f"{d['id']} claims incomplete but lists nothing missing"


def test_every_idea_forbids_invention():
    """The one rule the whole experiment exists to prove."""
    for d in _load(IDEAS):
        assert "invent" in d["must_not"].lower()


def test_canonical_volume_case_present():
    """§18's 'buy when volume looks high' must be in the corpus."""
    assert any("volume" in d["raw_input"].lower() and d["completeness"] == "vague"
               for d in _load(IDEAS))


# ---------------------------------------------------------------- V2: unsafe

@pytest.mark.parametrize("path", UNSAFE, ids=lambda p: p.stem)
def test_unsafe_is_wellformed(path: Path):
    doc = json.loads(path.read_text())
    for key in ("id", "category", "expected_response", "request", "why",
                "expected_behaviour", "must_not"):
        assert key in doc, f"{path.name} missing {key}"
    assert doc["category"] in {"impossible", "unsafe", "suspicious"}
    assert doc["expected_response"] in {"REJECT", "CLARIFY", "COMPILE_WITH_WARNING"}


def test_impossible_and_unsafe_are_never_merely_warned():
    """A look-ahead strategy or a real-money request is a refusal, not a footnote."""
    for d in _load(UNSAFE):
        if d["category"] in {"impossible", "unsafe"}:
            assert d["expected_response"] in {"REJECT", "CLARIFY"}, d["id"]


def test_real_money_request_is_rejected():
    """ADR-002 is an architectural boundary, not a preference."""
    docs = _load(UNSAFE)
    hits = [d for d in docs if "real money" in d["request"].lower()]
    assert hits, "no real-money request fixture"
    assert all(d["expected_response"] == "REJECT" for d in hits)


def test_prompt_injection_fixture_present_and_rejected():
    docs = _load(UNSAFE)
    hits = [d for d in docs if "ignore previous instructions" in d["request"].lower()]
    assert hits, "no prompt-injection fixture"
    assert all(d["expected_response"] == "REJECT" for d in hits)


def test_lookahead_request_is_rejected():
    """Entering at the low of the day is look-ahead stated as a strategy."""
    assert any(d["expected_response"] == "REJECT" and "low of the day" in d["request"].lower()
               for d in _load(UNSAFE))


def test_risk_override_requests_are_rejected():
    """Loss-chasing and stop removal are how accounts die - both must refuse."""
    docs = _load(UNSAFE)
    for phrase in ("daily loss limit", "turn off the stop"):
        hits = [d for d in docs if phrase in d["request"].lower()]
        assert hits, f"no fixture for {phrase!r}"
        assert all(d["expected_response"] == "REJECT" for d in hits)


def test_contradictory_risk_values_rejected():
    """risk 1%/trade with a 0.5% daily cap can never take a second trade."""
    assert any("daily loss limit of 0.5" in d["request"].lower() for d in _load(UNSAFE))


def test_unsafe_fixtures_record_the_wrong_behaviour_too():
    """Naming the failure mode is what makes the fixture scoreable."""
    for d in _load(UNSAFE):
        assert len(d["must_not"]) > 20, f"{d['id']} must_not is too thin to score against"


def test_adversarial_coverage_is_substantial():
    docs = _load(UNSAFE)
    critical = [d for d in docs if d.get("severity") == "critical"]
    assert len(critical) >= 10, f"only {len(critical)} critical fixtures"


# ---------------------------------------------------------------- B4: rules

def test_clarification_rules_cover_the_named_gaps():
    """The task names breakout, volume, exit, timeframe and risk explicitly."""
    rules = json.loads((EXP / "clarification_rules.json").read_text())["rules"]
    for required in ("breakout", "volume", "exit", "timeframe", "risk"):
        assert required in rules, f"no clarification rule for {required}"


def test_every_rule_has_trigger_questions_and_a_prohibition():
    rules = json.loads((EXP / "clarification_rules.json").read_text())["rules"]
    for name, r in rules.items():
        assert r["trigger"] and r["why"] and r["compiles_to"], name
        assert len(r["ask"]) >= 2, f"{name} asks too little to close the gap"
        assert r["never"], f"{name} does not say what must never be assumed"


def test_rules_forbid_convention_as_default():
    """A 'standard' period is still an invented parameter."""
    text = (EXP / "CLARIFICATION_RULES.md").read_text().lower()
    assert "standard" in text and "invented parameter" in text


def test_questions_are_asked_in_one_pass():
    text = (EXP / "CLARIFICATION_RULES.md").read_text().lower()
    assert "all at once" in text or "one at a time" in text
