"""Write path for the QuantForge Discord bots.

The chat path (bots.ask_hermes) is deliberately read-only: it advises and never
touches disk. This module is the ONLY way a bot changes code, and it is
deliberately narrow.

Shape of a build:

    1. fetch origin, create a fresh git WORKTREE off origin/main on a new branch
       bot/<who>/<slug>-<id>. The bot never works in the shared checkout, so a
       build can never corrupt main or collide with a human's uncommitted work.
    2. run the `hermes` CLI inside that worktree with write toolsets enabled.
    3. run the test suite. The result is reported verbatim, pass or fail.
    4. inspect `git diff --name-only` against the bot's ALLOWED SCOPE and a
       global forbidden list. Secrets-shaped paths abort the whole build.
    5. commit anything the agent left uncommitted, push the branch, open a PR.
    6. remove the worktree. The branch and PR survive for human review.

Nothing merges itself. A human reviews and merges — ADR-011.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("builder")

# Long, because a real implementation task is not a chat reply. The hermes CLI
# is killed at this bound and the build reports a timeout rather than hanging
# the Discord interaction forever.
BUILD_TIMEOUT = 45 * 60
TEST_TIMEOUT = 15 * 60
GIT_TIMEOUT = 180

# One build at a time across BOTH bots: they share one repo, one ssh agent and
# one GitHub token. Parallel builds produce interleaved pushes and confusing PRs.
BUILD_LOCK = asyncio.Semaphore(1)

# Paths each persona may change. Enforced after the fact on the real diff, not
# left to the model's goodwill - the prompt asks, this checks. Registered in
# SCOPES below; adding a bot without a scope entry gives it nothing, by design.
DIRECTOR_SCOPE = (
    "research/", "experiments/", "packages/strategy_schema/",
    "packages/exchange_contracts/", "data-contracts/", "tests/", "docs/",
)
ADMIN_SCOPE = (
    "services/", "scripts/", "infra/", ".github/", "docs/", "tests/",
    "packages/risk_engine/", "pyproject.toml", "requirements.txt",
)
# The Builder writes specs, schema and fixtures - the StrategySpec contract and
# the corpus that exercises it. Deliberately NARROWER than the Director: it must
# not touch the backtester or validation, because a bot that both authors a spec
# and edits the engine that judges it can make its own output look correct.
BUILDER_SCOPE = (
    "packages/strategy_schema/", "data-contracts/", "experiments/", "tests/",
)
# QA writes the validators and fixtures that make its checks executable, but not
# the schema or experiments it reviews - same self-marking fence as the Builder,
# pointed the other way.
QA_SCOPE = ("tests/", "data-contracts/")
# The Risk Reviewer writes the review criteria and the tests that make them
# executable - never the spec, the experiments or the backtester it critiques.
# A critic that can edit what it judges is marking its own homework from the
# other direction.
RISK_SCOPE = ("docs/", "tests/")
# The Strategy Analyst authors specs and the fixtures that exercise them, but
# NOT packages/strategy_schema/ - the schema its own output is validated
# against - and not research/, the backtester that grades the idea. An author
# who can widen the definition of "valid" passes every spec it writes.
ANALYST_SCOPE = ("experiments/", "data-contracts/", "tests/")

# Never, for any bot, on any branch. A build that touches one of these is
# aborted and discarded rather than pushed for review: the point of review is
# lost if the diff can already have leaked a credential into git history.
FORBIDDEN = (
    re.compile(r"(^|/)[^/]*\.env(\.|$)"),
    re.compile(r"\.(key|pem|p12|pfx)$"),
    re.compile(r"(^|/)credentials"),
    re.compile(r"(^|/)secrets?/"),
    re.compile(r"(^|/)\.git/"),
)

BUILD_RULES = """
YOU ARE IN BUILD MODE. Unlike the chat path, you DO have file and terminal
access, and you are inside a disposable git worktree on your own branch. What
you write here is real and will be pushed for human review.

Rules that still hold, without exception:
- PAPER/DEMO ONLY. Do not write code that places, routes or simulates a
  real-money order, and do not add live-exchange credentials or endpoints.
- You NEVER invent an unspecified strategy parameter. If the task is missing a
  value you need, do not guess a default: write nothing for that part, and say
  in your final message exactly which value you need.
- You NEVER write a performance number, backtest metric, Sharpe or win rate
  into a file unless the deterministic engine in this repo produced it during
  THIS build and you can point at the command that did.
- No secrets in code, tests, fixtures, comments or commit messages. Never read
  or copy anything from /root/.config.
- Stay inside this worktree. Do not touch /root/apps, other projects, the
  Hermes profile directories, or any path outside the repository root.
- Do not `git push`, do not open a pull request, do not merge, do not switch or
  delete branches. The service does that for you after it has checked your
  diff. A push from inside the agent bypasses that check.

Method:
- Read AGENTS.md, AI_PROJECT_CONTEXT.md and CURRENT_STATE.md before writing.
- Small coherent change. Tests land WITH the code, not after.
- Run the suite yourself before you finish:  .venv/bin/python -m pytest -q
- If the task conflicts with an ADR in docs/decisions/, STOP, change nothing,
  and explain the conflict. A refused build is a correct outcome.
- Leave your work as uncommitted changes or as commits on this branch. Either
  is fine.

Finish with a short plain-text summary: what you changed, which files, whether
the tests pass, and anything you deliberately did not do.
"""


# ------------------------------------------------------------------ read path
#
# The chat path gets REAL file reading, but never in the shared checkout: each
# bot owns a scratch worktree pinned to origin/main. Before every question the
# tree is hard-reset and cleaned, so anything a chat session writes is silently
# discarded and can never reach a human's working copy or a branch. Reads are
# genuine; writes are void. That asymmetry is the whole point — reading is safe
# and needs no review, writing is not and goes through build().

_READ_LOCKS: dict[str, asyncio.Lock] = {}


def read_lock(bot: str) -> asyncio.Lock:
    return _READ_LOCKS.setdefault(bot, asyncio.Lock())


async def ensure_read_tree(repo: Path, bot: str) -> Path | None:
    """Return a clean, up-to-date read-only worktree for `bot`, or None."""
    wt = repo / ".worktrees" / f"_read_{bot}"
    await _run(["git", "fetch", "origin", "main"], repo)
    if not (wt / ".git").exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        rc, out = await _run(
            ["git", "worktree", "add", "--detach", str(wt), "origin/main"], repo)
        if rc:
            log.warning("read tree for %s unavailable: %s", bot, out)
            return None
        return wt
    for cmd in (["git", "reset", "--hard", "origin/main"],
                ["git", "clean", "-fdx", "-e", ".venv"]):
        rc, out = await _run(cmd, wt)
        if rc:
            log.warning("read tree reset failed (%s): %s", bot, out)
            return None
    return wt


@dataclass
class BuildResult:
    ok: bool
    summary: str
    branch: str = ""
    pr_url: str = ""
    files: tuple[str, ...] = ()
    tests: str = ""
    out_of_scope: tuple[str, ...] = ()


def slugify(text: str, limit: int = 32) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:limit].rstrip("-")) or "task"


SCOPES: dict[str, tuple[str, ...]] = {
    "director": DIRECTOR_SCOPE,
    "admin": ADMIN_SCOPE,
    "builder": BUILDER_SCOPE,
    "qa": QA_SCOPE,
    "risk": RISK_SCOPE,
    "analyst": ANALYST_SCOPE,
}


def scope_for(bot: str) -> tuple[str, ...]:
    """Explicit lookup, never a fallback. An unknown bot gets the EMPTY scope, so
    every file it touches is flagged and the PR opens as a draft. A two-way
    `if bot == "director" else ADMIN_SCOPE` silently handed any new bot the
    Admin's write scope - the failure mode of a mistyped name must be too little
    authority, not someone else's."""
    return SCOPES.get(bot, ())


def classify(files: list[str], bot: str) -> tuple[list[str], list[str]]:
    """Split changed paths into (forbidden, out-of-scope-but-allowed-to-review)."""
    allowed = scope_for(bot)
    forbidden = [f for f in files if any(p.search(f) for p in FORBIDDEN)]
    outside = [f for f in files
               if f not in forbidden and not f.startswith(allowed)]
    return forbidden, outside


# Param is `timeout_s`, not `timeout`: asyncio.timeout (which ASYNC109 pushes you
# toward) cancels the await but leaves the child process running. These are git and
# pytest subprocesses - they must be killed, so wait_for + proc.kill() is correct.
async def _run(cmd: list[str], cwd: Path, timeout_s: int = GIT_TIMEOUT) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, f"timed out after {timeout_s}s"
    text = (out or b"").decode("utf-8", "replace")
    text = re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", text)
    return proc.returncode or 0, text.strip()


async def _cleanup(repo: Path, wt: Path, branch: str, keep_branch: bool) -> None:
    await _run(["git", "worktree", "remove", "--force", str(wt)], repo)
    if not keep_branch:
        await _run(["git", "branch", "-D", branch], repo)


async def build(
    *,
    repo: Path,
    bot: str,
    persona: str,
    task: str,
    who: str,
    hermes_bin: str,
    progress=None,
    history: str = "",
) -> BuildResult:
    """Run one supervised build. Returns a BuildResult; never raises for a
    failed build (only for a broken environment)."""

    async def say(msg: str) -> None:
        log.info("[%s] %s", bot, msg)
        if progress:
            await progress(msg)

    branch = f"bot/{bot}/{slugify(task)}-{uuid.uuid4().hex[:6]}"
    wt = repo / ".worktrees" / branch.replace("/", "_")

    async with BUILD_LOCK:
        rc, out = await _run(["git", "fetch", "origin", "main"], repo)
        if rc:
            return BuildResult(False, f"Could not fetch origin/main:\n{out}")

        wt.parent.mkdir(parents=True, exist_ok=True)
        rc, out = await _run(
            ["git", "worktree", "add", "-b", branch, str(wt), "origin/main"], repo)
        if rc:
            return BuildResult(False, f"Could not create worktree:\n{out}")

        await say(f"Working on `{branch}`. This takes a while — I'll report back.")

        try:
            prompt = (
                f"{persona}\n\n{BUILD_RULES}\n"
                f"{history}\n"
                f"Requested by {who} via Discord.\n"
                f"Branch: {branch}\n"
                f"TASK:\n{task}\n"
            )
            proc = await asyncio.create_subprocess_exec(
                hermes_bin, "-z", prompt,
                "-t", "file,terminal,code_execution,todo",
                # --in + --no-restore-cwd are LOAD-BEARING, not tidiness. The
                # hermes CLI restores the recorded cwd of a previous session on
                # startup: without these the agent silently walks out of its
                # worktree and edits the shared checkout, which is exactly the
                # containment this whole module exists to provide. Observed, not
                # theoretical - it wrote an ADR straight into main first try.
                "--in", str(wt), "--no-restore-cwd",
                "--yolo", "--accept-hooks",
                cwd=str(wt),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                raw, err = await asyncio.wait_for(proc.communicate(),
                                                  timeout=BUILD_TIMEOUT)
            except TimeoutError:
                proc.kill()
                await proc.wait()
                await _cleanup(repo, wt, branch, keep_branch=False)
                return BuildResult(
                    False,
                    f"Build timed out after {BUILD_TIMEOUT // 60} minutes. "
                    "Nothing was pushed and the branch was discarded — the task "
                    "was probably too large for one build. Split it up.")

            agent_msg = (raw or b"").decode("utf-8", "replace").strip()
            if not agent_msg:
                agent_msg = (err or b"").decode("utf-8", "replace").strip()
            agent_msg = re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", agent_msg).strip()

            # --- containment check: did the agent stay inside its worktree? ---
            # The CLI has been observed escaping to the shared checkout. If the
            # main working tree is dirty, we cannot tell the agent's work from a
            # human's, so refuse rather than commit someone else's changes.
            rc, dirty = await _run(["git", "status", "--porcelain"], repo)
            if dirty.strip():
                await _cleanup(repo, wt, branch, keep_branch=False)
                return BuildResult(
                    False,
                    "ABORTED — the shared checkout at "
                    f"{repo} has uncommitted changes, so I cannot prove the build "
                    "stayed inside its own worktree. Nothing was pushed. Clean or "
                    "commit the working tree and run /build again.\n"
                    + dirty[:600])

            # --- what actually changed on disk, not what the agent claims ---
            await _run(["git", "add", "-A"], wt)
            rc, staged = await _run(
                ["git", "diff", "--cached", "--name-only"], wt)
            rc2, committed = await _run(
                ["git", "diff", "--name-only", "origin/main...HEAD"], wt)
            files = sorted({f for f in (staged + "\n" + committed).split("\n") if f})

            if not files:
                await _cleanup(repo, wt, branch, keep_branch=False)
                return BuildResult(
                    False,
                    "No files changed, so there is nothing to review. The agent "
                    "said:\n\n" + agent_msg[:1200])

            forbidden, outside = classify(files, bot)
            if forbidden:
                await _cleanup(repo, wt, branch, keep_branch=False)
                return BuildResult(
                    False,
                    "ABORTED — the build touched paths that must never be "
                    "committed: " + ", ".join(forbidden) +
                    ". The branch was deleted and nothing was pushed.",
                    files=tuple(files), out_of_scope=tuple(forbidden))

            await say("Changes written. Running the test suite.")
            py = wt / ".venv" / "bin" / "python"
            if not py.exists():
                py = repo / ".venv" / "bin" / "python"
            rc, test_out = await _run([str(py), "-m", "pytest", "-q"], wt,
                                      timeout_s=TEST_TIMEOUT)
            tests_pass = rc == 0
            tail = "\n".join(test_out.split("\n")[-12:])

            # --- commit, push, PR ---
            await _run(["git", "commit", "-m",
                        f"{bot}: {task[:60]}\n\nRequested by {who} via Discord. "
                        f"Built by the {bot} bot; not human-authored."], wt)
            rc, out = await _run(["git", "push", "-u", "origin", branch], wt)
            if rc:
                await _cleanup(repo, wt, branch, keep_branch=True)
                return BuildResult(
                    False,
                    f"Wrote the changes but could not push `{branch}`:\n{out[:600]}\n"
                    "The branch exists locally; a human can push it.",
                    branch=branch, files=tuple(files), tests=tail)

            draft = bool(outside) or not tests_pass
            title = f"[{bot}] {task[:60]}"
            body = (
                f"Requested by **{who}** in Discord.\n\n"
                f"Built by the QuantForge {bot} bot (ADR-011). Not human-authored — "
                f"review before merging.\n\n"
                f"**Task**\n> {task[:800]}\n\n"
                f"**Tests:** {'pass' if tests_pass else 'FAIL'}\n```\n{tail[:1200]}\n```\n"
                f"**Agent summary**\n{agent_msg[:2000]}\n"
            )
            if outside:
                body += ("\n**Out of scope:** this bot is scoped to "
                         f"{', '.join(scope_for(bot))} but changed "
                         f"{', '.join(outside)}. Opened as a draft.\n")
            gh = shutil.which("gh")
            pr_url = ""
            if gh:
                cmd = [gh, "pr", "create", "--base", "main", "--head", branch,
                       "--title", title, "--body", body]
                if draft:
                    cmd.append("--draft")
                rc, out = await _run(cmd, wt)
                if rc == 0:
                    pr_url = out.strip().split("\n")[-1]
                else:
                    log.warning("gh pr create failed: %s", out)
            if not pr_url:
                rc, origin = await _run(["git", "remote", "get-url", "origin"], wt)
                slug = re.sub(r"^.*github\.com[:/]|\.git$", "", origin.strip())
                pr_url = (f"https://github.com/{slug}/compare/main...{branch}?expand=1"
                          "  (open it manually — the bot could not create the PR)")

            await _cleanup(repo, wt, branch, keep_branch=True)

            summary = (
                f"{'Draft PR' if draft else 'PR'} open: {pr_url}\n"
                f"Branch `{branch}` · {len(files)} file(s) · "
                f"tests {'pass' if tests_pass else 'FAIL'}\n"
                + (f"OUT OF SCOPE for me: {', '.join(outside)}\n" if outside else "")
                + "\n" + agent_msg[:900]
            )
            return BuildResult(tests_pass and not outside, summary, branch=branch,
                               pr_url=pr_url, files=tuple(files), tests=tail,
                               out_of_scope=tuple(outside))
        except Exception as exc:  # noqa: BLE001
            log.exception("build failed")
            await _cleanup(repo, wt, branch, keep_branch=False)
            return BuildResult(False, f"Build crashed: {type(exc).__name__}: {exc}")
