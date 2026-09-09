"""Live GitHub state, injected into every bot prompt.

WHY THIS EXISTS: repo_facts() reads the working tree on THIS host. That answers
"what files exist" but not "what has actually shipped" - and the bots kept
answering the second question from the first. A file present in the checkout may
be uncommitted local work; a branch pushed by a /build run is invisible to a
directory walk; a merged PR that changed the plan leaves no trace on disk at all.

GitHub is the shared truth for both AIOS environments (ADR-010), so the honest
answer to "what shipped" comes from the remote, not the filesystem. This module
fetches a small, bounded summary: recent commits on main, open PRs (including the
bot/* branches builds push), open issues, and any bot branches with no PR yet.

Everything here is best-effort and cached. GitHub being unreachable must degrade
an answer, never fail a reply - but the degraded prompt says so explicitly, so
the model reports "I cannot see GitHub right now" instead of inventing a
plausible commit history. That failure mode is the entire reason this file is
careful.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time

log = logging.getLogger("git_facts")

REMOTE = "CodoWIzard/Quantforge"

# GitHub state changes on the scale of minutes, and every bot mention would
# otherwise spend three subprocesses and ~2s of API latency re-fetching the same
# answer. A 5-minute cache keeps "what shipped" current enough to be useful while
# a burst of Discord questions costs one fetch, not thirty.
CACHE_TTL = 300
_cache: dict[str, tuple[float, str]] = {}
_lock = asyncio.Lock()

GH = shutil.which("gh") or "/usr/bin/gh"
GH_TIMEOUT = 20


async def _gh(*args: str) -> str | None:
    """Run a gh command, returning stdout or None. Never raises."""
    try:
        proc = await asyncio.create_subprocess_exec(
            GH, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=GH_TIMEOUT)
    except (TimeoutError, OSError, ValueError):
        log.warning("gh %s failed", " ".join(args[:2]), exc_info=True)
        return None
    if proc.returncode != 0:
        log.warning("gh %s rc=%s: %s", " ".join(args[:2]), proc.returncode,
                    (err or b"").decode("utf-8", "replace")[:200])
        return None
    return (out or b"").decode("utf-8", "replace").strip()


def _load(raw: str | None) -> list[dict]:
    """Parse a gh --json payload. A malformed body is treated as no data, never
    as an exception that would take down the whole prompt build."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("gh returned non-JSON")
        return []
    return data if isinstance(data, list) else []


async def _fetch() -> str:
    commits = _load(await _gh(
        "api", f"repos/{REMOTE}/commits?per_page=8",
        "--jq", "[.[] | {sha: .sha[0:7], msg: (.commit.message | split(\"\\n\")[0]), "
                "who: .commit.author.name, when: .commit.author.date[0:10]}]",
    ))
    prs = _load(await _gh(
        "pr", "list", "-R", REMOTE, "--state", "open", "--limit", "15",
        "--json", "number,title,headRefName,isDraft,author",
    ))
    issues = _load(await _gh(
        "issue", "list", "-R", REMOTE, "--state", "open", "--limit", "15",
        "--json", "number,title,labels",
    ))
    branches = _load(await _gh(
        "api", f"repos/{REMOTE}/branches?per_page=50",
        "--jq", "[.[] | select(.name | startswith(\"bot/\")) | {name: .name}]",
    ))

    # Total failure and "genuinely nothing open" are different states and must not
    # produce the same prompt: the first means do not answer, the second is an
    # answer. commits is the probe - a reachable repo always has commits.
    if not commits:
        return (
            "GITHUB STATE UNAVAILABLE. You cannot see the remote right now. If asked\n"
            "  what has shipped, what is open, or what a PR/issue says, say plainly that\n"
            "  you cannot reach GitHub at the moment. Do NOT answer from the local\n"
            "  checkout as if it were the remote, and do NOT invent commits, PR numbers\n"
            "  or issue numbers - a fabricated PR number sends someone hunting for a\n"
            "  page that does not exist.\n"
        )

    rows = [f"GITHUB STATE ({REMOTE}, fetched just now - this is what actually SHIPPED):"]

    rows.append("  Recent commits on main:")
    for c in commits[:8]:
        rows.append(f"    {c.get('sha','?')} {c.get('when','')} "
                    f"{c.get('who','?')}: {str(c.get('msg',''))[:90]}")

    if prs:
        rows.append("  OPEN pull requests (NOT merged - proposed, awaiting human review):")
        for p in prs:
            draft = " [DRAFT]" if p.get("isDraft") else ""
            who = (p.get("author") or {}).get("login", "?")
            rows.append(f"    #{p.get('number')}{draft} {str(p.get('title',''))[:70]}"
                        f"  ({p.get('headRefName','?')}, by {who})")
    else:
        rows.append("  OPEN pull requests: none.")

    if issues:
        rows.append("  OPEN issues:")
        for i in issues:
            labels = ",".join(lbl.get("name", "") for lbl in (i.get("labels") or []))
            rows.append(f"    #{i.get('number')} {str(i.get('title',''))[:70]}"
                        + (f"  [{labels}]" if labels else ""))
    else:
        rows.append("  OPEN issues: none.")

    # A bot/ branch with no PR is a /build that pushed but could not open the PR
    # (the fine-grained PAT cannot write to the partner's repo). Naming these stops
    # the bots reporting such a build as either finished or failed - it is neither.
    pr_refs = {p.get("headRefName") for p in prs}
    orphan = [b["name"] for b in branches
              if b.get("name") and b["name"] not in pr_refs]
    if orphan:
        rows.append("  Pushed bot branches with NO open PR (build landed, PR not opened -")
        rows.append("  a human must open it; do not call these merged or failed):")
        for name in orphan[:10]:
            rows.append(f"    {name}")

    rows.append(
        "  HOW TO READ THIS: an open PR is a PROPOSAL, not shipped work - never\n"
        "  describe its contents as if they are in main. Commits listed above ARE in\n"
        "  main. Anything absent from both lists has not shipped, whatever the local\n"
        "  checkout shows: uncommitted local files are not project state. Cite real\n"
        "  numbers from this block only - never guess a PR or issue number."
    )
    return "\n".join(rows) + "\n"


async def git_facts() -> str:
    """Cached GitHub summary for prompt injection. Never raises."""
    now = time.monotonic()
    hit = _cache.get("facts")
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    async with _lock:
        # Re-check inside the lock: a burst of concurrent mentions would otherwise
        # all miss the cache and each launch its own set of gh subprocesses.
        hit = _cache.get("facts")
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            return hit[1]
        try:
            text = await _fetch()
        except Exception:  # noqa: BLE001 - a prompt fragment must never kill a reply
            log.exception("git_facts fetch failed")
            text = ("GITHUB STATE UNAVAILABLE (internal error). Say you cannot reach\n"
                    "  GitHub; do not invent commits, PRs or issue numbers.\n")
        _cache["facts"] = (time.monotonic(), text)
        return text
