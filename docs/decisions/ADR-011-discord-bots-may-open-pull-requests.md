# ADR-011: Discord bots may open pull requests via the /build slash command

Status: Accepted
Date: 2026-09-08

## Decision

The two Discord bots (Admin Bot and Research Director Bot) are permitted to write and
commit code, but ONLY when invoked through the /build slash command. /build runs the
bot in an isolated git worktree branched from origin/main, checks the resulting diff
against a per-bot path-scope allowlist and a forbidden-secrets list, executes the full
test suite, and opens a pull request for human review. Nothing merges automatically.
Chat interactions remain strictly read-only: any code a bot writes in a chat reply is
ephemeral and has no effect on the repository.

## Rationale

Requiring all writes to pass through a structured, audited pipeline addresses three risks
that would be present if bots could commit freely:

1. Scope creep: bots modify files outside their designated ownership areas. The per-bot
   allowlist (Admin Bot owns services/, scripts/, infra/, .github/, packages/risk_engine/,
   tests/, docs/, and dependency manifests; Research Director owns research/, experiments/,
   packages/ strategy code, and data-contracts/) is enforced by the pipeline before a PR
   is opened. A diff that touches out-of-scope paths is opened as a draft PR and flagged
   for human triage rather than silently accepted.

2. Secret leakage: an LLM producing code could inadvertently embed a credential. The
   forbidden-secrets check scans every changed file before the PR is created and blocks
   the PR if a pattern matches.

3. Untested changes: the pipeline runs .venv/bin/python -m pytest -q before opening the
   PR. A failing suite surfaces immediately in the PR status and the Discord thread rather
   than reaching a reviewer invisibly.

Chat remaining read-only is essential for the audit trail. ADR-010 (GitHub is the shared
source of truth) requires that every consequential decision be versioned; a bot reply that
edits a file and disappears from context would break that guarantee.

## Alternatives considered

Bots may never write code: This was the original constraint and is the safest posture.
It was relaxed here because the internship team is two people; requiring every mechanical
change (scaffold a new test file, add an ADR, update a manifest) to go through a human
keyboard is a bottleneck that slows the experiment ladder without adding safety if the
pipeline guards are in place.

Bots may commit directly to main: Rejected. Human review of every diff is required under
the project's risk controls. A direct push to main bypasses that review and would violate
the intent of ADR-010.

Bots may open PRs from any branch without worktree isolation: Rejected. Shared mutable
state between concurrent bot invocations creates race conditions and makes the audit trail
ambiguous. Isolated worktrees mean each /build invocation is independent and reproducible.

Bots may merge their own PRs after tests pass: Rejected. At least one human approval is
required before merge. This preserves accountability and satisfies the internship
supervisors' expectation that no code reaches main without human eyes.

## Consequences

Every bot-authored change is traceable to a Discord thread ID, a branch, a PR and a test
result. The PR description records the invoking user (jaedyn or intern), the Discord
message ID and the bot persona that ran, so the audit trail satisfies ADR-010.

Chat bots must not describe a file they wrote in a chat reply as if it landed in the
repository. The correct instruction is: "run /build with this task". This ADR makes that
rule explicit and provides the rationale bots can cite when declining to write in chat.

Bot path-scope allowlists must be kept up to date as the directory structure evolves.
An out-of-date allowlist causes legitimate /build tasks to be opened as draft PRs; this
is recoverable but wastes reviewer time.

The forbidden-secrets scanner must be maintained alongside any new credential patterns
introduced into the project (new Azure resources, new API keys, etc.).

## Source

Established by the QuantForge team, 2026-09-08. Requested by jaedyn via Discord
(issue ref: dis-f15244).
