"""The bots must describe the repo from disk, never from memory.

Regression origin: the persona named the repo path but gave the model no way to READ
it. Asked "where does shipped work live?", the Research Director produced a confident,
entirely invented tree - /engine/, /validation/, /paper/, /docs/ADRs/, CONTRIBUTING.md.
Five of the seven paths it cited did not exist. It also implied components had shipped
when only their scaffolding exists.

A model told *about* a repository it cannot see will fill the gap with plausible
fiction. These tests lock the fix: real facts are read from disk and injected into
every prompt, and the anti-fabrication rule stays in the persona.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BOTS_DIR = REPO / "services" / "discord-bots"
sys.path.insert(0, str(BOTS_DIR))

bots = pytest.importorskip("bots", reason="discord.py not installed")

#: Paths the bot hallucinated. None of these exist; if one is ever created legitimately,
#: update this list AND the note inside repo_facts().
FABRICATED = ["/engine/", "/validation/", "/paper/", "/docs/ADRs/"]


def test_repo_facts_reads_real_directories():
    facts = bots.repo_facts()
    for real in ("packages/", "research/", "data-contracts/", "experiments/", "agents/"):
        assert real in facts, f"repo_facts omits {real}"


def test_repo_facts_names_the_true_adr_location():
    """ADRs are in docs/decisions/, not docs/ADRs/."""
    facts = bots.repo_facts()
    assert "docs/decisions/" in facts
    assert "ADR-001" in facts


def test_repo_facts_explicitly_denies_the_hallucinated_paths():
    """Naming them is what stops the model reaching for them again."""
    facts = bots.repo_facts()
    for bogus in ("engine", "validation", "paper"):
        assert bogus in facts.lower()
    assert "there is no" in facts.lower()


def test_hallucinated_directories_really_do_not_exist():
    """If this fails, the denial in repo_facts() has become a lie."""
    for name in ("engine", "paper"):
        assert not (REPO / name).exists(), f"{name}/ now exists - update repo_facts()"
    assert not (REPO / "docs" / "ADRs").exists()
    assert not (REPO / "CONTRIBUTING.md").exists()


def test_repo_facts_degrades_honestly_when_unreadable(monkeypatch):
    """An unreadable repo must produce a refusal, not silence that invites guessing."""
    monkeypatch.setattr(bots, "REPO", Path("/nonexistent_repo_xyz"))
    facts = bots.repo_facts()
    assert "UNAVAILABLE" in facts
    assert "guessing" in facts.lower()


def test_persona_forbids_describing_structure_from_memory():
    text = (BOTS_DIR / "bots.py").read_text()
    assert "NEVER describe repository structure" in text
    assert "from memory" in text


def test_persona_distinguishes_existing_from_planned():
    """Most of the repo is scaffolding whose bodies raise NotImplementedError."""
    text = (BOTS_DIR / "bots.py").read_text()
    assert "NotImplementedError" in text
    assert "PLANNED" in text


def test_facts_are_injected_into_every_prompt():
    """A fact function nobody calls fixes nothing."""
    text = (BOTS_DIR / "bots.py").read_text()
    assert "repo_facts()" in text.split("def ask_hermes")[1][:600]


def test_facts_report_existing_research_artifacts():
    """Second failure mode, opposite direction.

    After the anti-fabrication fix the bot stopped inventing paths - but then DENIED
    that B2/B4/V2 existed, because it read CURRENT_STATE.md ("no implementation
    exists") and collapsed research artifacts into code. Written fixtures are real
    deliverables; they must be confirmable.
    """
    facts = bots.repo_facts()
    assert "RESEARCH ARTIFACTS THAT EXIST" in facts
    assert "002-strategy-compiler" in facts
    assert "WRITTEN UP" in facts, "a written RESULT.md must not be reported as blank"


def test_facts_separate_the_three_states():
    """Code that runs / research artifacts / scaffolding are not the same thing."""
    facts = bots.repo_facts()
    for marker in ("CODE THAT RUNS", "RESEARCH ARTIFACTS", "SCAFFOLDING"):
        assert marker in facts
    low = facts.lower()
    assert "backtest" in low and "has ever run" in low
    assert "no performance metric" in low or "no metrics exist" in low


def test_experiment_002_result_is_actually_written():
    """Guards the claim the bot now makes on our behalf."""
    res = REPO / "experiments" / "002-strategy-compiler" / "RESULT.md"
    assert res.is_file()
    assert len(res.read_text().splitlines()) > 40


def test_current_state_records_the_completed_research():
    """The bot reads this file. If it omits shipped work, the bot denies shipped work."""
    text = (REPO / "CURRENT_STATE.md").read_text()
    for token in ("B2", "B4", "V2", "I001", "U001", "CLARIFICATION_RULES"):
        assert token in text, f"CURRENT_STATE.md does not mention {token}"


def test_facts_include_board_task_ids():
    """B2/B4/V2 are how humans refer to work in Discord.

    Without the board the bot found the right folder but said "I don't know what
    B2 B4 V2 refers to" while standing on the files.
    """
    facts = bots.repo_facts()
    assert "BOARD" in facts
    for task in ("[B1]", "[B2]", "[B3]", "[B4]", "[V1]", "[V2]", "[V3]"):
        assert task in facts, f"board task {task} missing from facts"


def test_facts_map_task_ids_to_files():
    facts = bots.repo_facts()
    assert "Task IDs map to files" in facts
    assert "ideas/" in facts and "CLARIFICATION_RULES.md" in facts


def test_facts_show_done_status():
    """Done vs open must come from the board, not from the model's impression."""
    facts = bots.repo_facts()
    assert "DONE" in facts and "open" in facts


def test_board_failure_is_announced_not_silent(monkeypatch, tmp_path):
    """A missing board must forbid guessing, not vanish from the prompt."""
    monkeypatch.setattr(bots, "REPO", tmp_path)
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "experiments").mkdir()
    facts = bots.repo_facts()
    assert "BOARD UNAVAILABLE" in facts or "UNAVAILABLE" in facts


def test_persona_states_chat_cannot_write_code():
    """The bot was asked to implement B3 and stalled 3 minutes instead of refusing.

    Chat shells out to a read-only CLI call and returns text - it cannot commit or
    open a PR. Since /build exists, the honest answer is no longer "I cannot write
    code" but "chat cannot; run /build" - so the persona must name the route rather
    than deny the capability, and must still never imply work is happening now.
    """
    text = (BOTS_DIR / "bots.py").read_text()
    assert "IN THIS CHAT YOU CAN READ CODE BUT NOT WRITE IT" in text
    assert "/build" in text
    assert "NEVER imply work is underway" in text
    assert "There is no background process" in text


def test_persona_admits_no_conversation_memory():
    """Each message is a cold start. Denying a quoted earlier answer confuses users."""
    text = (BOTS_DIR / "bots.py").read_text()
    assert "NO memory of previous messages" in text


def test_timeout_message_blames_the_bot_not_the_user():
    """'Try a narrower question' told Jayden his question was the problem. It wasn't."""
    text = (BOTS_DIR / "bots.py").read_text()
    assert "my failure" in text
    assert "Try a narrower question." not in text


def test_timeout_has_headroom_for_long_pastes():
    assert bots.HERMES_TIMEOUT >= 300, "180s was not enough for a 9KB brief"


def test_no_duplicate_hyphen_and_underscore_packages():
    """Python cannot import a hyphenated module; empty twins confuse the layout."""
    pkgs = {p.name for p in (REPO / "packages").iterdir() if p.is_dir()}
    for name in pkgs:
        assert "-" not in name, f"packages/{name} is not importable - use underscores"
