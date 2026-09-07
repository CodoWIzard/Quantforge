"""Agent behavioural contracts are load-bearing text - assert they still say the key things.

An instructions file can be edited casually. These tests make deleting a safety rule a
failing build rather than a quiet regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parent.parent / "agents"
ROLES = ["research-director", "strategy-specialist", "critic"]


@pytest.mark.parametrize("role", ROLES)
def test_agent_has_all_four_files(role: str):
    d = AGENTS / role
    for name in ("README.md", "instructions.md", "tools.json", "output.schema.json"):
        assert (d / name).is_file(), f"{role} is missing {name}"


@pytest.mark.parametrize("role", ROLES)
def test_tool_allowlist_denies_dangerous_capabilities(role: str):
    """§34: no generic run-any-shell / call-any-URL / access-any-secret tool."""
    doc = json.loads((AGENTS / role / "tools.json").read_text())
    forbidden = set(doc["forbidden"])
    assert {"shell", "http_request", "read_secret"} <= forbidden
    assert not set(doc["allowed_tools"]) & forbidden


@pytest.mark.parametrize("role", ROLES)
def test_instructions_forbid_acting_on_injected_text(role: str):
    """§18: instructions arriving inside data are data, not commands."""
    text = (AGENTS / role / "instructions.md").read_text().lower()
    assert "untrusted" in text or "injection" in text


def test_specialist_may_not_invent_parameters():
    """The single most important rule in the whole system (AGENTS.md)."""
    text = (AGENTS / "strategy-specialist" / "instructions.md").read_text().lower()
    assert "invent" in text
    assert "default" in text


def test_critic_may_not_optimise_while_judging():
    """§15: a critic that repairs the strategy is no longer an independent reviewer."""
    text = (AGENTS / "critic" / "instructions.md").read_text().lower()
    assert "optimise" in text or "optimize" in text


def test_director_cannot_claim_untool_ed_metrics():
    """AI never computes authoritative metrics."""
    text = (AGENTS / "research-director" / "instructions.md").read_text().lower()
    assert "metric" in text


def test_evaluation_fixtures_exist_and_are_wellformed():
    fixtures = sorted((AGENTS / "evals" / "fixtures").glob("*.json"))
    assert fixtures, "no evaluation fixtures - §17 requires them before serious build"
    for path in fixtures:
        doc = json.loads(path.read_text())
        for key in ("id", "agent", "scenario", "expected_behaviour", "failure_mode", "assertions"):
            assert key in doc, f"{path.name} missing {key}"
        assert doc["agent"] in ROLES + ["data-auditor", "research-planner",
                                        "risk-reviewer", "report-explainer"]


def test_injection_fixture_is_present():
    """Adversarial coverage is where the product's credibility lives."""
    ids = {json.loads(p.read_text())["id"]
           for p in (AGENTS / "evals" / "fixtures").glob("*.json")}
    assert any("injection" in i for i in ids)
