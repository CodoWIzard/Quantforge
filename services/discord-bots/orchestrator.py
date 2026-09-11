"""Single-agent research pipeline: Director intake -> spec -> critique -> verdict.

WHY THIS EXISTS: the personas were written to hand work to each other - the
Analyst ends with "HANDOFF TO RISK REVIEWER", the Reviewer with "HANDOFF TO
RESEARCH DIRECTOR" - but nothing ever carried those handoffs. Each bot only woke
on a human @mention, so the human was the transport: copy the spec, paste it at
the next bot, copy the critique, paste it back. The chain existed on paper and
was performed by hand, which is exactly the kind of gap that gets described in
Discord as if it were working.

This module executes the chain. One command, four stages.

ADR-011: the stages are now all the DIRECTOR in different modes (Intake,
StrategySpec, Skeptical Critic, Report) rather than four separate bots. The
Analyst, Risk Reviewer and QA bot remain live for direct @mention, but they are
no longer wired into /research.

WHAT THIS COSTS, stated plainly because it is the whole risk of the change:
the Director now marks its own homework. Stage 2 authors the StrategySpec and
stage 3 attacks it. Every persona in this project was deliberately scoped to
exclude what it judges - an author who can widen the definition of "valid"
passes every spec it writes - and merging those roles removes that separation.

Two things hold the line instead, and neither is as strong as an independent
reviewer:
  1. The critic stage is told explicitly that it wrote the spec, that nothing
     independent sits behind it, and to argue as if a rival wrote the text.
  2. The verdict stage must tell the user that every stage was the same agent.
     A four-stage transcript otherwise reads as four opinions.

The real replacement is the deterministic validator layer (ADR-011); until those
eleven tools exist, a /research run is one agent's reasoning, presented as such.

DESIGN CONSTRAINTS, each one load-bearing:

- The pipeline is a FIXED LIST, not a bot deciding who to call next. Agents that
  choose their own successor can loop (A hands to B, B hands back to A) and the
  loop is expensive, hard to stop and produces confident nonsense at the end. A
  fixed sequence cannot cycle. If a stage wants more work it says so in its
  output and a human starts another run.
- Every stage sees the ORIGINAL user idea plus the FULL text of prior stages.
  Passing a summary forward is how the user's actual idea gets replaced by a
  tidier one three hops later, with nobody able to point at where it changed.
  This matters MORE now, not less: one agent re-reading its own words is exactly
  how a messy idea drifts into a tidy one nobody asked for.
- One run at a time, globally. The stages share the hermes backend, one OAuth
  token and the read worktrees; parallel runs interleave into nonsense.
- A failed stage ABORTS the run. Continuing with a hole means the Director
  produces a verdict over evidence it never received, which is worse than no
  verdict - the output looks complete either way.
- Nothing here trades, writes code or merges anything. Code changes are /build
  only, which still runs through the Builder, opens a PR and is untouched by
  this module.
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
        label="1/4 Director — intake & framing",
        brief=(
            "A user has submitted the trading idea below. You are opening a research\n"
            "run. This is INTAKE MODE only: do NOT write the StrategySpec yet - that\n"
            "is the next stage, and it will receive this output verbatim.\n\n"
            "In under 250 words: state what the idea actually claims, name every\n"
            "parameter that is undefined (entry, exit, timeframe, sizing, risk per\n"
            "trade, session), and set explicit direction for what the spec stage must\n"
            "specify and what it must leave marked unknown. If the idea is outside\n"
            "BTC/ETH perps or needs live money, say so now rather than at the end."
        ),
    ),
    Stage(
        bot="director",
        label="2/4 Director — StrategySpec Mode",
        brief=(
            "STRATEGYSPEC MODE. Your own framing is above. Produce ONE StrategySpec\n"
            "covering market, timeframe, direction, entry, exit, risk and assumptions.\n\n"
            "Preserve the user's idea exactly - do not substitute a tidier or more\n"
            "backtestable strategy for the one they described. Any field nobody stated\n"
            "is marked MISSING with the question that would resolve it; it is never\n"
            "filled with a default, and 'the most conservative reading' means SMALLER\n"
            "RISK, not whichever reading would test better.\n\n"
            "You are now the author. The next stage attacks this text, so write it to\n"
            "be attacked: state each rule precisely enough to be proven wrong.\n"
            "End by naming what the critic stage should try hardest to falsify."
        ),
    ),
    Stage(
        bot="director",
        label="3/4 Director — Skeptical Critic Mode",
        brief=(
            "SKEPTICAL CRITIC MODE. This overrides your usual helpful posture for this\n"
            "stage only.\n\n"
            "WARNING - YOU WROTE THE SPEC ABOVE. You are now marking your own work,\n"
            "and the standing failure mode is going easy on it. Until the deterministic\n"
            "validators exist there is no independent check behind you: whatever you\n"
            "fail to catch here is not caught at all. Argue against yourself as if a\n"
            "rival analyst wrote that spec and you were paid to find the hole.\n\n"
            "Falsification, not improvement. Do NOT rewrite the strategy. Work through:\n"
            "look-ahead bias, overfitting, sample size, unrealistic fees or slippage,\n"
            "vague rules that cannot be coded, regime dependence, hidden leverage or\n"
            "liquidation risk, and any field you filled that the user never stated.\n\n"
            "Separately and explicitly, run the CONTRACT CHECK a dedicated QA stage\n"
            "used to run: are all required fields present, is every value inside the\n"
            "allowed scope (BTC/ETH perps, 1m/5m/15m), is any rule invented rather\n"
            "than supplied, is the spec specific enough to be demonstrated? Report\n"
            "structural defects separately from strategy weaknesses - they are\n"
            "different findings and the next stage must not blur them.\n\n"
            "Report defects. Do not fix them. No backtest has run, so no performance\n"
            "number exists - do not imply one."
        ),
    ),
    Stage(
        bot="director",
        label="4/4 Director — verdict",
        brief=(
            "REPORT MODE. You have the whole chain: the user's idea, your framing,\n"
            "your StrategySpec and your own critique. Close the run for the user in\n"
            "PLAIN ENGLISH.\n\n"
            "Give a verdict - pass, caution, fail, needs_clarification or blocked -\n"
            "and say plainly what it rests on. Keep the two kinds of finding apart:\n"
            "whether the spec is STRUCTURALLY valid (fields, scope, invented rules) is\n"
            "a different question from whether the IDEA survives scrutiny. A spec can\n"
            "be perfectly well-formed and still be a bad strategy - never let a clean\n"
            "contract check read as an endorsement.\n\n"
            "State one thing explicitly: every stage of this run was you. Nothing here\n"
            "was independently reviewed, and the deterministic validators that will\n"
            "eventually check this do not exist yet (ADR-011). Say so in the verdict,\n"
            "because a four-stage transcript looks like four opinions.\n\n"
            "State what must be tested before anyone trusts this, and the specific\n"
            "question the user must answer for the spec to be complete. No performance\n"
            "numbers exist - no backtest has run - so do not imply any. Address the\n"
            "user directly."
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

    The `-----` lines are DELIMITERS, and the prompt says so explicitly. A live
    run had a stage open its answer by echoing `----- OUTPUT OF STAGE: 3/4 ... -----`
    back as if it were the required format: shown a structured transcript and no
    statement of what that structure is, a model imitates it. Every framing
    convention a prompt uses on the model must be named as such, or it is read as
    an instruction.
    """
    parts = [
        "RESEARCH RUN IN PROGRESS - a fixed sequence of stages. Every stage is the",
        "same agent in a different mode (ADR-011); this is not four opinions.",
        "You are ONE stage. Your output is passed verbatim to the next stage and is",
        "posted publicly in the Discord channel under your own name.",
        "",
        "The ----- lines below delimit context that already exists. They are not a",
        "template: do NOT reproduce them, and do NOT open your answer with a stage",
        "header. Write only your own stage's content.",
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
