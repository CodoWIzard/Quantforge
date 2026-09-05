"""Contract tests for the Discord bot service.

These lock the safety-critical invariants from the Master Blueprint so a future
edit cannot quietly regress them. Pure static/AST analysis — no network, no
Discord connection, no running process required.

Run:  .venv/bin/python -m pytest tests/ -q
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "services" / "discord-bots" / "bots.py"


@pytest.fixture(scope="module")
def src() -> str:
    return SRC.read_text()


@pytest.fixture(scope="module")
def tree(src: str) -> ast.Module:
    return ast.parse(src)


@pytest.fixture(scope="module")
def funcs(tree: ast.Module) -> dict[str, ast.AsyncFunctionDef]:
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)}


def body(src: str, fn: ast.AST) -> str:
    return ast.get_source_segment(src, fn) or ""


# --- backend invocation -------------------------------------------------

def test_hermes_called_without_invalid_toolset_flag(src: str) -> None:
    """`-t none` is rejected by the hermes CLI and silently yields no output."""
    assert '"-t", "none"' not in src
    assert not re.search(r'HERMES,\s*"-z",\s*prompt,\s*"-t"', src)


def test_hermes_invoked_via_argv_not_shell(src: str) -> None:
    """No shell interpolation of user-controlled prompt text."""
    assert "create_subprocess_exec" in src
    assert "create_subprocess_shell" not in src


def test_backend_call_has_timeout(src: str) -> None:
    assert "asyncio.wait_for" in src
    assert "HERMES_TIMEOUT" in src


# --- Optional-safety (the Pyright regressions) --------------------------

@pytest.mark.parametrize("fn", ["on_ready", "on_message"])
def test_self_user_is_guarded(src: str, funcs, fn: str) -> None:
    """discord.Client.user is None until READY; never deref it directly."""
    seg = body(src, funcs[fn])
    assert "self.user." not in seg, f"{fn} dereferences Optional self.user"
    assert re.search(r"\bme\s*=\s*self\.user\b", seg), f"{fn} must bind me = self.user"


def test_on_message_returns_early_when_not_ready(src: str, funcs) -> None:
    assert re.search(r"if\s+me\s+is\s+None", body(src, funcs["on_message"]))


def test_no_optional_user_deref_anywhere(src: str) -> None:
    assert not re.search(r"self\.user\.\w", src)


# --- loop safety --------------------------------------------------------

def test_bot_ignores_other_bots(src: str, funcs) -> None:
    """Two bots in one guild will infinitely reply to each other otherwise."""
    assert "msg.author.bot" in body(src, funcs["on_message"])


def test_replies_only_on_explicit_address(src: str, funcs) -> None:
    seg = body(src, funcs["on_message"])
    assert "mentioned" in seg and "replying" in seg
    assert re.search(r"if\s+not\s+\(mentioned\s+or\s+replying\)", seg)


# --- persona guardrails (ADR-002 / ADR-003) -----------------------------

@pytest.mark.parametrize("rule", [
    "NEVER produce authoritative numeric results",
    "NEVER place, modify or simulate orders",
    "NEVER invent an unspecified strategy parameter",
])
def test_shared_context_states_hard_rule(src: str, rule: str) -> None:
    assert rule in src, f"missing guardrail: {rule}"


def test_context_forbids_credential_disclosure(src: str) -> None:
    assert "Never reveal credentials" in src


def test_both_personas_inherit_shared_context(src: str) -> None:
    assert re.search(r"^DIRECTOR = CONTEXT \+", src, re.M)
    assert re.search(r"^ADMIN = CONTEXT \+", src, re.M)


# --- secret hygiene -----------------------------------------------------

def test_no_hardcoded_tokens(src: str) -> None:
    """Discord bot tokens start with the base64 of the app's snowflake id."""
    assert not re.search(r"MTU0NDY[0-9A-Za-z._-]{20,}", src)


def test_tokens_loaded_from_mode_600_file(src: str) -> None:
    assert "discord.env" in src
    assert "/root/.config/quantforge" in src


# --- discord message limits --------------------------------------------

def test_output_truncated_below_discord_cap(src: str) -> None:
    m = re.search(r"MAX_DISCORD\s*=\s*(\d+)", src)
    assert m and int(m.group(1)) <= 2000
