"""Contract tests for GitHub context injection (services/discord-bots/git_facts.py)
and the live-persona roster (bots.roster_facts).

Both exist because of the same class of bug: a bot answering confidently from
the wrong source. git_facts was added because repo_facts() shows the local
checkout, and the bots reported uncommitted local files as shipped project
state while being blind to the branches their own builds pushed. roster_facts
was added because the Director, asked about the newly-live Risk Reviewer, read
the agents/ directory - instruction drafts for a future pipeline - and reported
that the Risk Reviewer did not exist, while it was running.

The critical property in both is the failure path: when the source cannot be
read, the prompt must SAY so, because a silent gap is what the model fills with
plausible fiction.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

BOTS_DIR = Path(__file__).resolve().parents[1] / "services" / "discord-bots"
sys.path.insert(0, str(BOTS_DIR))

import git_facts  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clear_cache():
    git_facts._cache.clear()
    yield
    git_facts._cache.clear()


# --- the failure path is the important one --------------------------------

def test_unreachable_github_says_so_instead_of_guessing(monkeypatch) -> None:
    """No commits back = cannot see the remote. The prompt must forbid answering
    from the local checkout, or the bot reports local state as shipped."""
    async def dead(*args):
        return None

    monkeypatch.setattr(git_facts, "_gh", dead)
    text = run(git_facts.git_facts())
    assert "GITHUB STATE UNAVAILABLE" in text
    assert "cannot reach GitHub" in text
    assert "do NOT invent commits" in text


def test_internal_error_still_produces_a_safe_prompt(monkeypatch) -> None:
    """A bug in the fetch must degrade the answer, never kill the reply."""
    async def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(git_facts, "_fetch", boom)
    text = run(git_facts.git_facts())
    assert "UNAVAILABLE" in text
    assert "do not invent" in text.lower()


def test_gh_failure_returns_none_rather_than_raising(monkeypatch) -> None:
    """_gh is called four times per fetch; any of them raising would take down
    the whole prompt build and with it the bot's reply."""
    async def explode(*args, **kwargs):
        raise OSError("no gh binary")

    monkeypatch.setattr(git_facts.asyncio, "create_subprocess_exec", explode)
    assert run(git_facts._gh("api", "whatever")) is None


def test_malformed_json_is_treated_as_no_data() -> None:
    assert git_facts._load("not json at all") == []
    assert git_facts._load(None) == []
    assert git_facts._load('{"not": "a list"}') == []


# --- shipped vs proposed --------------------------------------------------

def test_open_prs_are_labelled_as_not_shipped(monkeypatch) -> None:
    """The recurring confusion: an open PR described as if it were in main."""
    async def fake(*args):
        if args[0] == "api" and "commits" in args[1]:
            return '[{"sha":"abc1234","msg":"a commit","who":"x","when":"2026-09-09"}]'
        if args[0] == "pr":
            return ('[{"number":7,"title":"Add thing","headRefName":"bot/x",'
                    '"isDraft":true,"author":{"login":"bot"}}]')
        return "[]"

    monkeypatch.setattr(git_facts, "_gh", fake)
    text = run(git_facts.git_facts())
    assert "#7" in text
    assert "[DRAFT]" in text
    assert "NOT merged" in text
    assert "an open PR is a PROPOSAL" in text


def test_local_checkout_does_not_outrank_the_remote(monkeypatch) -> None:
    """Uncommitted local files are not project state; the prompt has to say it."""
    async def fake(*args):
        if args[0] == "api" and "commits" in args[1]:
            return '[{"sha":"abc1234","msg":"m","who":"w","when":"2026-09-09"}]'
        return "[]"

    monkeypatch.setattr(git_facts, "_gh", fake)
    text = run(git_facts.git_facts())
    assert "uncommitted local files are not project state" in text


def test_pushed_branch_without_a_pr_is_called_out(monkeypatch) -> None:
    """A /build that pushed but could not open the PR is neither merged nor
    failed, and gets reported as one or the other unless named."""
    async def fake(*args):
        if args[0] == "api" and "commits" in args[1]:
            return '[{"sha":"abc1234","msg":"m","who":"w","when":"2026-09-09"}]'
        if args[0] == "api" and "branches" in args[1]:
            return '[{"name":"bot/admin/orphaned-branch"}]'
        return "[]"

    monkeypatch.setattr(git_facts, "_gh", fake)
    text = run(git_facts.git_facts())
    assert "bot/admin/orphaned-branch" in text
    assert "do not call these merged or failed" in text


def test_no_open_work_is_stated_positively(monkeypatch) -> None:
    """'None open' and 'cannot see GitHub' are different answers."""
    async def fake(*args):
        if args[0] == "api" and "commits" in args[1]:
            return '[{"sha":"abc1234","msg":"m","who":"w","when":"2026-09-09"}]'
        return "[]"

    monkeypatch.setattr(git_facts, "_gh", fake)
    text = run(git_facts.git_facts())
    assert "OPEN pull requests: none." in text
    assert "OPEN issues: none." in text
    assert "UNAVAILABLE" not in text


# --- caching --------------------------------------------------------------

def test_result_is_cached_so_a_burst_costs_one_fetch(monkeypatch) -> None:
    calls = []

    async def counted():
        calls.append(1)
        return "FACTS"

    monkeypatch.setattr(git_facts, "_fetch", counted)

    async def many():
        return await asyncio.gather(*(git_facts.git_facts() for _ in range(5)))

    out = run(many())
    assert out == ["FACTS"] * 5
    assert len(calls) == 1, "concurrent misses must collapse into one fetch"


def test_cache_ttl_is_bounded() -> None:
    """Stale GitHub state is its own kind of wrong answer."""
    assert 0 < git_facts.CACHE_TTL <= 900


# --- the roster -----------------------------------------------------------

pytest.importorskip("discord")
import bots  # noqa: E402


def test_every_running_persona_is_in_the_registry() -> None:
    """PERSONAS drives the orchestrator; a bot missing here cannot be a stage."""
    src = (BOTS_DIR / "bots.py").read_text()
    for name in ("director", "admin", "builder", "qa", "risk", "analyst"):
        assert name in bots.PERSONAS, f"{name} missing from PERSONAS"
        assert f'QFBot("{name}"' in src


def test_registry_maps_to_the_real_persona_strings() -> None:
    assert bots.PERSONAS["risk"] is bots.RISK
    assert bots.PERSONAS["analyst"] is bots.ANALYST
    assert bots.PERSONAS["director"] is bots.DIRECTOR


def test_roster_names_every_live_bot() -> None:
    text = bots.roster_facts()
    for display in ("Research_Director", "Strategy-Analyst", "Risk-Reviewer",
                    "QA-bot", "Builder_1", "Admin-bot"):
        assert display in text


def test_roster_separates_live_bots_from_the_agents_directory() -> None:
    """The exact confusion that made the Director deny a running bot existed."""
    text = bots.roster_facts()
    assert "DO NOT confuse these with the agents/ directory" in text
    assert "NEVER been run against a model" in text
    assert "A role missing from agents/ can still be" in text


def test_roster_states_that_handoffs_are_not_automatic_outside_a_run() -> None:
    """Without this a bot says 'I'll pass this to the Analyst', which never
    happens - nothing runs after its reply ends."""
    text = bots.roster_facts()
    assert "NO automatic handoff" in text
    assert "never imply you have passed it on" in text


def test_roster_documents_the_research_chain() -> None:
    text = bots.roster_facts()
    assert "/research" in text
    assert "Analyst writes the StrategySpec" in text


def test_both_fact_blocks_reach_the_prompt() -> None:
    """git_facts and roster_facts are useless if not injected."""
    src = (BOTS_DIR / "bots.py").read_text()
    start = src.index("async def ask_hermes")
    window = src[start:start + 1200]
    assert "repo_facts()" in window
    assert "roster_facts()" in window
    assert "git_facts.git_facts()" in window


# --- message splitting: the truncation bug the live run exposed -----------

def test_short_text_is_not_split() -> None:
    assert bots.split_message("hello", 100) == ["hello"]


def test_long_text_is_split_not_truncated() -> None:
    """A pipeline stage published to Discord must appear in FULL, or the public
    trail stops matching what the next stage actually received."""
    text = "\n".join(f"line {i}" for i in range(500))
    parts = bots.split_message(text, 200)
    assert len(parts) > 1
    rejoined = "\n".join(parts)
    assert rejoined.replace("\n", "") == text.replace("\n", ""), "no content lost"
    assert all(len(p) <= 200 for p in parts)


def test_split_prefers_line_boundaries() -> None:
    """Severing a StrategySpec mid-bullet makes the section unreadable."""
    text = "\n".join(["a" * 50] * 20)
    parts = bots.split_message(text, 120)
    assert all(not p.startswith("a" * 50 + "a") for p in parts)


def test_unbroken_run_is_hard_split_rather_than_lost() -> None:
    text = "x" * 1000
    parts = bots.split_message(text, 100)
    assert "".join(parts) == text
    assert all(len(p) <= 100 for p in parts)


def test_ask_hermes_limit_is_a_parameter_not_a_constant() -> None:
    """The orchestrator raises it; chat keeps the Discord default."""
    src = (BOTS_DIR / "bots.py").read_text()
    assert "limit: int = MAX_DISCORD" in src
    assert "text[:limit]" in src
