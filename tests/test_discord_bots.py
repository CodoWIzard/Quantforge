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


def test_chat_path_gets_read_tools_only(src: str, funcs) -> None:
    """Chat may READ the repo. It must never get write/exec tools: only /build,
    which runs in a disposable worktree and opens a PR, is allowed to change code."""
    seg = body(src, funcs["ask_hermes"])
    assert '"-t", "file"' in seg, "chat path must request the read-only file toolset"
    for banned in ("terminal", "code_execution", "--yolo"):
        assert banned not in seg, f"chat path must not enable {banned}"


def test_chat_path_runs_in_disposable_worktree(src: str, funcs) -> None:
    """Never run chat in the shared checkout: a stray write would land in a
    human's working copy.

    cwd= alone does not hold: the hermes CLI restores a previous session's
    recorded cwd on startup, which walks the process back into the main
    checkout. --in + --no-restore-cwd are what actually pin it.
    """
    seg = body(src, funcs["ask_hermes"])
    assert "ensure_read_tree" in seg and "read_lock" in seg
    assert '"--in", str(cwd), "--no-restore-cwd"' in seg


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


# --- venue (ADR-012) ----------------------------------------------------

def test_context_names_both_venues_and_retires_kraken(src: str) -> None:
    """The CONTEXT scope line is what most directly steers a generated
    StrategySpec. A whole live /research run wrote "Kraken demo" throughout,
    correctly, because this line said so long after the decision had changed:
    the agents read the repo, so a venue decided only in chat does not exist.
    ADR-012 fixed the line; this test stops it drifting back."""
    ctx = src[src.index("CONTEXT = "):src.index("CONTEXT = ") + 3000]
    assert "BINANCE" in ctx, "market data venue must be named"
    assert "TRADINGVIEW" in ctx, "paper execution venue must be named"
    assert "Kraken is NO LONGER a venue" in ctx


def test_context_warns_that_stale_kraken_references_remain(src: str) -> None:
    """Naming the new venues is not enough on its own. exchange_contracts and its
    tests still hold real Kraken symbols and tick sizes, deliberately (ADR-012:
    renaming them into Binance tickers would carry Kraken's ticks across and
    fabricate fills). A bot that reads those files without being told they are
    stale will quote them as current."""
    assert "treat any Kraken reference you read as stale" in src


def test_context_states_data_and_execution_are_different_venues(src: str) -> None:
    """Binance data + TradingView fills is not one venue, and the difference is
    not cosmetic: a paper fill no longer evidences that the fill was available in
    the data that triggered it. Nothing in the code detects that, so the bots
    must not present one as confirming the other."""
    assert "not evidence the same fill existed in the data" in src


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
