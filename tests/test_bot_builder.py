"""Contract tests for the bot write path (services/discord-bots/builder.py).

The builder is the only route by which an LLM changes this repository, so its
guardrails are tested two ways: statically (the source cannot be edited to drop
a rule) and behaviourally (the path classifier really rejects what it claims).

No network, no Discord, no `hermes` invocation.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

SVC = Path(__file__).resolve().parents[1] / "services" / "discord-bots"
SRC_PATH = SVC / "builder.py"
sys.path.insert(0, str(SVC))

import builder  # noqa: E402


@pytest.fixture(scope="module")
def src() -> str:
    return SRC_PATH.read_text()


# --- path guard behaviour ----------------------------------------------

@pytest.mark.parametrize("path", [
    ".env",
    "services/discord-bots/.env",
    "config/prod.env",
    "keys/deploy.pem",
    "certs/server.key",
    "credentials.json",
    "infra/secrets/azure.yaml",
    "secret/token.txt",
])
def test_secret_shaped_paths_are_forbidden(path: str) -> None:
    forbidden, _ = builder.classify([path], "admin")
    assert forbidden == [path], f"{path} must be refused, not reviewed"


def test_unknown_bot_gets_no_write_scope() -> None:
    """A mistyped or newly added bot name must fall to the EMPTY scope, not
    inherit the Admin's. Too little authority is a draft PR; too much is a bot
    quietly editing infrastructure it was never granted."""
    assert builder.scope_for("typo-bot") == ()
    _, outside = builder.classify(["services/discord-bots/bots.py"], "typo-bot")
    assert outside == ["services/discord-bots/bots.py"]


def test_every_running_bot_has_an_explicit_scope() -> None:
    """bots.py starts three personas; a persona with no SCOPES entry can never
    open a clean PR, which would be a silent, confusing failure."""
    for name in ("director", "admin", "builder"):
        assert builder.scope_for(name), f"{name} has no write scope"


def test_builder_cannot_edit_the_engine_that_judges_its_specs() -> None:
    """Authoring a StrategySpec and editing the backtester/validation that grades
    it is self-marking. Those paths belong to the Director."""
    for path in ("research/backtester/engine.py",
                 "research/validation/verdict.py"):
        _, outside = builder.classify([path], "builder")
        assert outside == [path]


@pytest.mark.parametrize("path", [
    "packages/strategy_schema/models.py",
    "data-contracts/strategy_spec.json",
    "experiments/002-strategy-compiler/fixtures.json",
    "tests/test_strategy_compiler.py",
])
def test_builder_owns_spec_schema_and_fixtures(path: str) -> None:
    forbidden, outside = builder.classify([path], "builder")
    assert not forbidden and not outside


@pytest.mark.parametrize("bot,path", [
    ("director", "research/backtester/engine.py"),
    ("director", "experiments/003-x/RESULT.md"),
    ("director", "packages/strategy_schema/models.py"),
    ("director", "tests/test_backtester.py"),
    ("admin", "services/discord-bots/bots.py"),
    ("admin", ".github/workflows/ci.yml"),
    ("admin", "packages/risk_engine/pre_trade.py"),
    ("admin", "pyproject.toml"),
])
def test_in_scope_paths_pass_clean(bot: str, path: str) -> None:
    forbidden, outside = builder.classify([path], bot)
    assert not forbidden and not outside


@pytest.mark.parametrize("bot,path", [
    ("director", "services/discord-bots/bots.py"),
    ("director", ".github/workflows/ci.yml"),
    ("admin", "research/backtester/engine.py"),
    ("admin", "experiments/002-strategy-compiler/run_b5_evidence.py"),
])
def test_cross_role_edits_are_flagged_not_silent(bot: str, path: str) -> None:
    """Each bot owns half the tree. Straying is allowed but must surface as a
    flagged draft PR, never as a clean one."""
    forbidden, outside = builder.classify([path], bot)
    assert not forbidden
    assert outside == [path]


def test_forbidden_beats_scope() -> None:
    """A secret inside an otherwise in-scope directory is still a hard refusal."""
    forbidden, outside = builder.classify(["services/discord-bots/.env"], "admin")
    assert forbidden and not outside


def test_scopes_do_not_grant_repo_root() -> None:
    """An empty-string entry would make str.startswith match every path."""
    for bot in ("director", "admin"):
        assert "" not in builder.scope_for(bot)
    forbidden, outside = builder.classify(["AGENTS.md"], "director")
    assert outside == ["AGENTS.md"]


def test_slugify_produces_safe_branch_component() -> None:
    slug = builder.slugify("Fix the ../../etc/passwd bug!! (urgent) $(rm -rf /)")
    assert re.fullmatch(r"[a-z0-9-]+", slug)
    assert ".." not in slug and "/" not in slug


def test_slugify_never_returns_empty() -> None:
    assert builder.slugify("!!!!") == "task"


# --- static guardrails --------------------------------------------------

def test_builds_are_serialised(src: str) -> None:
    """Both bots share one repo, one token and one ssh agent."""
    assert re.search(r"BUILD_LOCK\s*=\s*asyncio\.Semaphore\(1\)", src)
    assert "async with BUILD_LOCK" in src


def test_build_uses_isolated_worktree_off_origin_main(src: str) -> None:
    assert '"git", "worktree", "add", "-b"' in src
    assert '"git", "fetch", "origin", "main"' in src


def test_diff_is_read_from_git_not_from_the_agent(src: str) -> None:
    """The scope check must inspect the real diff; an agent's self-report of
    which files it touched is not evidence."""
    assert '"git", "diff", "--cached", "--name-only"' in src
    assert "origin/main...HEAD" in src


def test_forbidden_diff_aborts_before_push(src: str) -> None:
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "build")
    seg = ast.get_source_segment(src, fn) or ""
    abort = seg.index("if forbidden:")
    push = seg.index('"git", "push"')
    assert abort < push, "forbidden-path check must run before the push"


def test_failing_tests_do_not_produce_a_clean_pr(src: str) -> None:
    assert "tests_pass = rc == 0" in src
    assert re.search(r"draft\s*=\s*bool\(outside\)\s*or\s*not\s*tests_pass", src)


def test_nothing_merges_itself(src: str) -> None:
    assert '"merge"' not in src
    assert "pr merge" not in src
    assert "--admin" not in src


def test_build_rules_state_the_hard_boundaries(src: str) -> None:
    for rule in ("PAPER/DEMO ONLY",
                 "NEVER invent an unspecified strategy parameter",
                 "No secrets in code",
                 "do not open a pull request"):
        assert rule in builder.BUILD_RULES, f"missing build rule: {rule}"


def test_timeouts_bound_every_subprocess(src: str) -> None:
    assert "asyncio.wait_for" in src
    for name in ("BUILD_TIMEOUT", "TEST_TIMEOUT", "GIT_TIMEOUT"):
        assert re.search(rf"{name}\s*=", src)


def test_git_invoked_via_argv_not_shell(src: str) -> None:
    assert "create_subprocess_shell" not in src


def test_agent_is_pinned_into_its_worktree(src: str) -> None:
    """REGRESSION: cwd= alone is not enough. The hermes CLI restores the recorded
    cwd of a previous session at startup, so the first real build wrote its file
    into the shared checkout instead of the branch. --in + --no-restore-cwd pin it."""
    assert '"--in", str(wt), "--no-restore-cwd"' in src


def test_escape_from_the_worktree_aborts_the_build(src: str) -> None:
    """If the shared checkout is dirty we cannot attribute the changes, so the
    build must refuse rather than push or silently drop them."""
    assert '"git", "status", "--porcelain"' in src
    fn_start = src.index("async def build(")
    body_src = src[fn_start:]
    guard = body_src.index("if dirty.strip():")
    push = body_src.index('"git", "push"')
    assert guard < push


def test_read_tree_is_reset_before_reuse(src: str) -> None:
    """A chat session's stray writes must not persist into the next question."""
    assert '"git", "reset", "--hard", "origin/main"' in src
    assert '"git", "clean", "-fdx"' in src
