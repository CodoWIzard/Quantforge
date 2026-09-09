"""Multi-bot research pipeline: Director -> Analyst -> Risk Reviewer -> Director.

WHY THIS EXISTS: the personas were written to hand work to each other - the
Analyst ends with "HANDOFF TO RISK REVIEWER", the Reviewer with "HANDOFF TO
RESEARCH DIRECTOR" - but nothing ever carried those handoffs. Each bot only woke
on a human @mention, so the human was the transport: copy the spec, paste it at
the next bot, copy the critique, paste it back. The chain existed on paper and
was performed by hand, which is exactly the kind of gap that gets described in
Discord as if it were working.

This module executes the chain. One command, four stages, each bot speaking under
its own identity in the channel so the audit trail is visible rather than
summarised by a single narrator.

DESIGN CONSTRAINTS, each one load-bearing:

- The pipeline is a FIXED LIST, not a bot deciding who to call next. Agents that
  choose their own successor can loop (A hands to B, B hands back to A) and the
  loop is expensive, hard to stop and produces confident nonsense at the end. A
  fixed sequence cannot cycle. If a stage wants more work it says so in its
  output and a human starts another run.
- Every stage sees the ORIGINAL user idea plus the FULL text of prior stages.
  Passing a summary forward is how the user's actual idea gets replaced by a
  tidier one three hops later, with nobody able to point at where it changed.
- One run at a time, globally. The stages share the hermes backend, one OAuth
  token and the read worktrees; parallel runs interleave into nonsense.
- A failed stage ABORTS the run. Continuing with a hole means the Director
  produces a verdict over evidence it never received, which is worse than no
  verdict - the output looks complete either way.
- Nothing here trades, writes code or merges anything. It is a conversation
  conducted in public, and every guardrail in the personas still applies because
  each stage is the same ask_hermes call a human @mention would make.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

log = logging.getLogger("orchestrator")

# One research run at a time across the whole process. See module docstring.
RUN_LOCK = asyncio.Semaphore(1)

# A whole run is four model calls; each can take minutes on a long idea. This cap
# exists so a wedged backend cannot hold the lock forever and block every later
# run - it bounds the damage, it is not a normal exit path.
RUN_TIMEOUT = 1800

# Hard ceiling on stages, independent of PIPELINE's length. PIPELINE is a
# constant today, but this is the guard that survives someone later making the
# sequence dynamic: a run can never cost more than this many model calls.
MAX_STAGES = 8

# Chat replies are capped at Discord's message length, but a pipeline stage's
# output is INPUT to the next stage. Truncating a StrategySpec at 1900 characters
# would hand the Risk Reviewer a spec cut off mid-section, and it would review the
# fragment without knowing anything was missing - a summary travelling in place of
# the work, which is the failure this pipeline was built to remove. Stages are
# fetched whole and split only when published.
STAGE_LIMIT = 20000


@dataclass(frozen=True)
class Stage:
    """One step: which bot speaks, and what it is being asked to do.

    `brief` is prepended to the accumulated context. It states the stage's job in
    workflow terms; the bot's own persona still supplies all its rules, so a
    stage cannot quietly relax a guardrail.
    """
    bot: str
    label: str
    brief: str


PIPELINE: tuple[Stage, ...] = (
    Stage(
        bot="director",
        label="1/5 Research Director — framing",
        brief=(
            "A user has submitted the trading idea below. You are opening a research\n"
            "run. Do NOT write the StrategySpec yourself - the Strategy Analyst does\n"
            "that next, and it will receive your output verbatim.\n\n"
            "Your job here, in under 250 words: state what the idea actually claims,\n"
            "name every parameter that is undefined (entry, exit, timeframe, sizing,\n"
            "risk per trade, session), and give the Analyst explicit direction on what\n"
            "to specify and what to leave marked as unknown. If the idea is outside\n"
            "BTC/ETH perps or needs live money, say so now rather than at the end."
        ),
    ),
    Stage(
        bot="analyst",
        label="2/5 Strategy Analyst — StrategySpec",
        brief=(
            "The Research Director has framed this idea for you above. Produce ONE\n"
            "StrategySpec in your required format, following the Director's direction.\n"
            "Preserve the user's idea - do not substitute a tidier strategy for it, and\n"
            "do not fill in a value nobody stated. End with your handoff naming what\n"
            "the Risk Reviewer should try hardest to falsify."
        ),
    ),
    Stage(
        bot="risk",
        label="3/5 Risk Reviewer — falsification",
        brief=(
            "Review the StrategySpec above in your required format. It was produced by\n"
            "the Strategy Analyst from the user's idea, both of which are shown. Your\n"
            "job is falsification, not improvement: find where this breaks. Do not\n"
            "rewrite the strategy, and do not approve it because it reads plausibly.\n"
            "End with your handoff to the Research Director."
        ),
    ),
    Stage(
        bot="qa",
        label="4/5 QA-bot — contract gate",
        brief=(
            "You now have the full chain: the user's idea, the Director's framing, the\n"
            "Analyst's StrategySpec and the Risk Reviewer's critique. Run your six\n"
            "checks (JSON/schema validity, required fields, scope, invented rules,\n"
            "clarification behaviour, demonstrability) against the StrategySpec the\n"
            "Analyst produced.\n\n"
            "You are a GATE, not the closing word: the Director speaks to the user after\n"
            "you, so write for the Director, not for the user. Output your review in the\n"
            "required JSON format. required_fixes names exactly what must be corrected;\n"
            "approval_summary is the one sentence the Director will act on.\n"
            "No performance numbers exist - no backtest has run - do not imply any.\n"
            "THE ONE THING YOU MUST NEVER DO IS FIX ANYTHING. Report defects; do not\n"
            "supply missing values or rewrite the strategy."
        ),
    ),
    Stage(
        bot="director",
        label="5/5 Research Director — verdict",
        brief=(
            "You now have the whole chain: the user's idea, your framing, the Analyst's\n"
            "StrategySpec, the Risk Reviewer's critique and QA's contract gate. Close\n"
            "the run for the user in PLAIN ENGLISH - they should never have to read\n"
            "QA's JSON to understand the answer.\n\n"
            "Give a verdict and say plainly what it rests on. Separate the two kinds of\n"
            "finding you were given: QA reports whether the spec is STRUCTURALLY valid\n"
            "(fields, schema, invented rules); the Risk Reviewer reports whether the\n"
            "IDEA survives scrutiny. A spec can pass QA and still be a bad strategy -\n"
            "do not let a clean contract check read as an endorsement.\n\n"
            "State what must be tested before anyone trusts this, and what specific\n"
            "question the user has to answer for the spec to be complete. No performance\n"
            "numbers exist - no backtest has run - so do not imply any. If you are\n"
            "overriding something QA or the Reviewer raised, say why. Address the user\n"
            "directly."
        ),
    ),
)


@dataclass
class StageResult:
    stage: Stage
    text: str
    seconds: float


@dataclass
class RunResult:
    ok: bool
    summary: str
    stages: list[StageResult] = field(default_factory=list)
    failed_at: str = ""


def build_context(idea: str, who: str, done: list[StageResult]) -> str:
    """The prompt body for the next stage: the original idea, then every prior
    stage in full.

    Full text, never a summary. A summarised handoff is how a strategy quietly
    becomes a different strategy: each hop drops the caveats, and by the verdict
    nobody can say which stage introduced the change.
    """
    parts = [
        "RESEARCH RUN IN PROGRESS - this is an automated multi-agent pipeline.",
        "You are one stage. Your output is passed verbatim to the next stage and is",
        "posted publicly in the Discord channel under your own name.",
        "",
        f"ORIGINAL USER IDEA (from {who}) - this is the thing being specified;",
        "no stage may replace it with a different idea:",
        f"    {idea}",
        "",
    ]
    for r in done:
        parts += [
            f"----- OUTPUT OF STAGE: {r.stage.label} -----",
            r.text,
            "",
        ]
    return "\n".join(parts)


async def run_pipeline(
    idea: str,
    who: str,
    channel: str,
    ask: Callable[..., Awaitable[str]],
    personas: dict[str, str],
    post: Callable[[str, str, str], Awaitable[None]],
    pipeline: tuple[Stage, ...] = PIPELINE,
) -> RunResult:
    """Execute the chain.

    `ask` is the same ask_hermes a human @mention uses - deliberately, so a
    pipeline stage cannot behave differently from the bot you can interrogate by
    hand. `post(bot, label, text)` publishes a stage under that bot's identity.
    Both are injected so the whole flow is testable without Discord or a model.
    """
    if len(pipeline) > MAX_STAGES:
        return RunResult(ok=False,
                         summary=f"Pipeline too long ({len(pipeline)} > {MAX_STAGES}).")

    missing = [s.bot for s in pipeline if s.bot not in personas]
    if missing:
        # Fail before spending anything. A typo'd bot name mid-run would abort at
        # stage three having already burned two model calls and posted half a
        # conversation the user has to mentally discard.
        return RunResult(ok=False,
                         summary=f"Unknown bot(s) in pipeline: {', '.join(missing)}.")

    done: list[StageResult] = []
    async with RUN_LOCK:
        started = time.monotonic()
        for stage in pipeline:
            if time.monotonic() - started > RUN_TIMEOUT:
                return RunResult(
                    ok=False, stages=done, failed_at=stage.label,
                    summary=(f"Run exceeded {RUN_TIMEOUT // 60} minutes and stopped at "
                             f"{stage.label}. Stages completed before that are above and "
                             f"remain valid; nothing was written or traded."),
                )

            context = build_context(idea, who, done)
            question = f"{context}\n{stage.brief}"
            log.info("stage %s (%s) starting", stage.label, stage.bot)
            t0 = time.monotonic()
            try:
                text = await ask(
                    personas[stage.bot], question, who, channel,
                    bot=stage.bot, history="", limit=STAGE_LIMIT,
                )
            except Exception as exc:  # noqa: BLE001 - one stage must not crash the bot
                log.exception("stage %s failed", stage.label)
                return RunResult(
                    ok=False, stages=done, failed_at=stage.label,
                    summary=(f"Stage {stage.label} failed ({type(exc).__name__}). The run "
                             f"stopped there - later stages did NOT run, so do not read "
                             f"the output above as a completed review."),
                )

            elapsed = time.monotonic() - t0
            text = (text or "").strip()
            if not text:
                # An empty answer is indistinguishable from a stage that decided
                # there was nothing to say, and the next stage would silently
                # proceed on missing evidence. Stop instead.
                return RunResult(
                    ok=False, stages=done, failed_at=stage.label,
                    summary=(f"Stage {stage.label} returned nothing. Run stopped; later "
                             f"stages did not run."),
                )

            result = StageResult(stage=stage, text=text, seconds=elapsed)
            done.append(result)
            try:
                await post(stage.bot, stage.label, text)
            except Exception:  # noqa: BLE001 - a Discord hiccup must not void the work
                log.exception("could not post stage %s", stage.label)

    total = sum(r.seconds for r in done)
    return RunResult(
        ok=True, stages=done,
        summary=(f"Research run complete — {len(done)} stages in {total / 60:.1f} min. "
                 f"Verdict is in the Research Director's final message above. "
                 f"No backtest ran and no order was placed."),
    )
