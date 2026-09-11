"""Contract tests for the research orchestrator (services/discord-bots/orchestrator.py).

The orchestrator's failure modes are not crashes - they are runs that LOOK
complete. A stage that dies silently, a summary passed forward instead of the
full text, or a verdict rendered over evidence that never arrived all produce a
tidy transcript with a hole in it. These tests pin the properties that make the
chain trustworthy: fixed sequence (no agent picks its own successor, so no
loops), full context forward, abort-on-failure, and one run at a time.

No network, no Discord, no model. `ask` and `post` are injected fakes.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

BOTS_DIR = Path(__file__).resolve().parents[1] / "services" / "discord-bots"
sys.path.insert(0, str(BOTS_DIR))

import orchestrator as orch  # noqa: E402

# The /research chain is Director-only (ADR-011). The other personas stay in the
# map because they remain live for direct @mention and /build; the pipeline just
# no longer routes to them.
PERSONAS = {"director": "D-PERSONA", "analyst": "A-PERSONA",
            "risk": "R-PERSONA", "qa": "QA-PERSONA", "builder": "B-PERSONA"}


def run(coro):
    return asyncio.run(coro)


class Recorder:
    """Captures what each stage was asked and what got posted."""

    def __init__(self, answers: dict[str, str] | None = None,
                 fail_on: str | None = None, empty_on: str | None = None,
                 per_stage: list[str] | None = None,
                 fail_stage: int | None = None, empty_stage: int | None = None):
        self.asks: list[tuple[str, str, str]] = []   # (bot, persona, question)
        self.posts: list[tuple[str, str, str]] = []  # (bot, label, text)
        self.answers = answers or {}
        self.fail_on = fail_on
        self.empty_on = empty_on
        # Every stage is now the same bot, so failures and answers are addressed
        # by STAGE INDEX. Keying by bot name would hit all four at once.
        self.per_stage = per_stage or []
        self.fail_stage = fail_stage
        self.empty_stage = empty_stage

    async def ask(self, persona, question, who, channel, bot="director", history="",
                  limit=1900):
        idx = len(self.asks)
        self.asks.append((bot, persona, question))
        if bot == self.fail_on or idx == self.fail_stage:
            raise RuntimeError("backend exploded")
        if bot == self.empty_on or idx == self.empty_stage:
            return "   "
        if idx < len(self.per_stage):
            return self.per_stage[idx]
        return self.answers.get(bot, f"[{bot} output]")

    async def post(self, bot, label, text):
        self.posts.append((bot, label, text))


# --- the pipeline shape itself -------------------------------------------

def test_pipeline_is_a_fixed_sequence_not_agent_chosen() -> None:
    """No stage names its own successor. A fixed tuple cannot cycle; agents that
    pick the next agent can hand work back and forth indefinitely."""
    assert isinstance(orch.PIPELINE, tuple)
    assert [s.bot for s in orch.PIPELINE] == ["director"] * 4


def test_research_chain_is_director_only() -> None:
    """ADR-011: the Analyst, Risk Reviewer and QA bot are no longer wired into
    /research. They stay alive for direct @mention; this asserts the CHAIN, not
    their existence."""
    assert {s.bot for s in orch.PIPELINE} == {"director"}


def test_builder_is_not_in_the_research_chain() -> None:
    """The Builder was never a /research stage and must not become one. /research
    is a conversation; /build is the only path that writes code, and it opens a
    PR for human review. Wiring the Builder in here would let a research run
    author code with no diff, no scope check and no PR."""
    assert "builder" not in [s.bot for s in orch.PIPELINE]


def test_director_opens_and_closes_the_run() -> None:
    """The run must end on a human-facing stage. Historically this guarded
    against ending on QA, whose output is a fenced JSON blob written for a
    machine; the rule outlives that pipeline."""
    assert orch.PIPELINE[0].bot == "director"
    assert orch.PIPELINE[-1].bot == "director"


def test_contract_check_survived_the_loss_of_the_qa_stage() -> None:
    """Absorbing QA must not silently drop what QA did.

    The QA stage ran six checks; if merging it into the critic stage just
    deleted them, the pipeline would lose its structural gate while still
    producing a confident verdict. The critic brief must still demand the
    contract check, and demand it be reported SEPARATELY from strategy
    weaknesses - a spec can be well-formed and still be a bad idea.
    """
    critic = orch.PIPELINE[2].brief
    assert "CONTRACT CHECK" in critic
    assert "invented rather" in critic
    assert "separately from strategy weaknesses" in critic
    assert "PLAIN ENGLISH" in orch.PIPELINE[-1].brief


def test_critic_stage_is_told_it_is_marking_its_own_work() -> None:
    """The whole risk of a single-agent chain: the author grades the author.

    Every persona here was scoped to exclude what it judges. Merging the roles
    removes that separation, so the prompt has to carry what the architecture no
    longer does - name the conflict, and say nothing independent sits behind it.
    """
    critic = orch.PIPELINE[2].brief
    assert "YOU WROTE THE SPEC ABOVE" in critic
    assert "no independent check behind you" in critic


def test_verdict_discloses_that_one_agent_ran_every_stage() -> None:
    """A four-stage transcript reads as four opinions unless it says otherwise."""
    final = orch.PIPELINE[-1].brief
    assert "every stage of this run was you" in final
    assert "independently reviewed" in final


def test_verdict_separates_structural_validity_from_idea_quality() -> None:
    """The failure this guards: a passing schema check reading as approval of
    the strategy."""
    final = orch.PIPELINE[-1].brief
    assert "well-formed and still be a bad strategy" in final


def test_stage_count_is_capped_independently_of_pipeline() -> None:
    """MAX_STAGES bounds cost even if someone later makes the sequence dynamic."""
    assert len(orch.PIPELINE) <= orch.MAX_STAGES


def test_an_over_long_pipeline_is_refused_before_spending_anything() -> None:
    rec = Recorder()
    long_pipeline = tuple(
        orch.Stage(bot="director", label=f"s{i}", brief="x")
        for i in range(orch.MAX_STAGES + 1)
    )
    res = run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post,
                                pipeline=long_pipeline))
    assert not res.ok
    assert not rec.asks, "must refuse before calling the model"


def test_unknown_bot_fails_before_any_model_call() -> None:
    """A typo'd bot name must not abort mid-run having already burned two calls
    and posted half a conversation."""
    rec = Recorder()
    bad = (orch.Stage(bot="director", label="a", brief="x"),
           orch.Stage(bot="nope", label="b", brief="x"))
    res = run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post,
                                pipeline=bad))
    assert not res.ok
    assert "nope" in res.summary
    assert not rec.asks


# --- context propagation: the substitution guard --------------------------

def test_every_stage_receives_the_original_user_idea() -> None:
    """The idea must reach the last stage unmediated. If only the previous
    stage's output travels, the user's actual idea can be replaced en route and
    nobody can point at the hop where it changed."""
    rec = Recorder()
    idea = "buy BTC when the 50 crosses the 200 on 5m"
    run(orch.run_pipeline(idea, "jayden", "research", rec.ask, PERSONAS, rec.post))
    assert len(rec.asks) == len(orch.PIPELINE)
    for _bot, _persona, question in rec.asks:
        assert idea in question


def test_each_stage_sees_all_previous_stage_outputs_in_full() -> None:
    rec = Recorder(per_stage=["FRAMING-TEXT", "SPEC-TEXT", "CRITIQUE-TEXT", "VERDICT"])
    run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    final_question = rec.asks[-1][2]
    for prior in ("FRAMING-TEXT", "SPEC-TEXT", "CRITIQUE-TEXT"):
        assert prior in final_question, "verdict stage must see the whole chain"


def test_first_stage_has_no_prior_output() -> None:
    rec = Recorder()
    run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    assert "OUTPUT OF STAGE" not in rec.asks[0][2]


def test_each_stage_runs_under_its_own_persona() -> None:
    """A stage must carry the persona of the bot doing it. Now that every stage
    is the Director, the mode lives in the brief - but the persona (and its
    guardrails) must still be attached to every call."""
    rec = Recorder()
    run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    got = [(bot, persona) for bot, persona, _ in rec.asks]
    assert got == [("director", "D-PERSONA")] * 4


def test_context_labels_the_idea_as_unreplaceable() -> None:
    ctx = orch.build_context("my idea", "jayden", [])
    assert "no stage may replace it" in ctx


def test_context_names_the_delimiter_as_a_delimiter() -> None:
    """A live run had a stage open its answer with `----- OUTPUT OF STAGE: 3/4 -----`,
    copying the transcript's framing as if it were the required output format.
    Shown structure and never told what it is, a model imitates it. The context
    must say the ----- lines delimit prior work and must not be reproduced."""
    ctx = orch.build_context("my idea", "jayden", [
        orch.StageResult(stage=orch.PIPELINE[0], text="PRIOR", seconds=1.0),
    ])
    assert "delimit" in ctx
    assert "do NOT reproduce them" in ctx
    assert "do NOT open your answer with a stage" in ctx
    # The instruction has to arrive BEFORE the thing it describes, or the model
    # has already read the pattern unlabelled.
    assert ctx.index("delimit") < ctx.index("----- OUTPUT OF STAGE")


# --- failure handling: a hole must not look like a result -----------------

def test_a_failing_stage_aborts_the_run() -> None:
    """Continuing past a failure would let the Director deliver a verdict over
    evidence it never received - and the output would look complete."""
    rec = Recorder(fail_stage=1)
    res = run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    assert not res.ok
    assert len(rec.asks) == 2, "must not run later stages"
    assert len(res.stages) == 1


def test_failure_summary_says_later_stages_did_not_run(orchestrate=None) -> None:
    """The user must not read a partial transcript as a finished review."""
    rec = Recorder(fail_stage=2)
    res = run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    assert "did NOT run" in res.summary or "did not run" in res.summary
    assert res.failed_at


def test_an_empty_stage_answer_stops_the_run() -> None:
    """Empty is indistinguishable from 'nothing to say', and the next stage
    would proceed on missing evidence without noticing."""
    rec = Recorder(empty_stage=1)
    res = run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    assert not res.ok
    assert len(res.stages) == 1


def test_a_post_failure_does_not_void_completed_work() -> None:
    """Discord hiccuping must not discard model output already paid for."""
    rec = Recorder()

    async def broken_post(bot, label, text):
        raise RuntimeError("discord down")

    res = run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, broken_post))
    assert res.ok
    assert len(res.stages) == len(orch.PIPELINE)


# --- publication ----------------------------------------------------------

def test_every_stage_is_posted_under_the_bot_that_produced_it() -> None:
    """A chain narrated entirely by one bot reads as that bot's account of what
    the others said; the visible trail is the point."""
    rec = Recorder()
    run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    assert [b for b, _, _ in rec.posts] == ["director"] * 4


def test_stage_labels_are_ordered_and_visible() -> None:
    labels = [s.label for s in orch.PIPELINE]
    n = len(orch.PIPELINE)
    assert all(lbl.startswith(f"{i}/{n}") for i, lbl in enumerate(labels, start=1))


# --- concurrency ----------------------------------------------------------

def test_only_one_run_executes_at_a_time() -> None:
    """Stages share the hermes backend, one OAuth token and the read worktrees;
    interleaved runs produce interleaved transcripts."""
    assert orch.RUN_LOCK._value == 1

    order: list[str] = []

    async def slow_ask(persona, question, who, channel, bot="director", history="",
                       limit=1900):
        order.append(f"start-{channel}")
        await asyncio.sleep(0.01)
        order.append(f"end-{channel}")
        return "x"

    async def noop_post(bot, label, text):
        pass

    async def both():
        await asyncio.gather(
            orch.run_pipeline("i", "u", "A", slow_ask, PERSONAS, noop_post),
            orch.run_pipeline("i", "u", "B", slow_ask, PERSONAS, noop_post),
        )

    run(both())
    # Run A's stages must all finish before run B's begin (or vice versa).
    first = order[0].split("-")[1]
    boundary = next(i for i, e in enumerate(order) if e.endswith(f"-{first}") is False)
    assert all(e.endswith(f"-{first}") for e in order[:boundary])


# --- the run does not trade or write --------------------------------------

def test_success_summary_states_nothing_was_executed() -> None:
    rec = Recorder()
    res = run(orch.run_pipeline("idea", "u", "c", rec.ask, PERSONAS, rec.post))
    assert res.ok
    assert "No backtest ran" in res.summary
    assert "no order was placed" in res.summary


def test_stages_are_fetched_whole_not_at_discord_length() -> None:
    """THE BUG THIS CAUGHT: the first live run truncated every stage at Discord's
    1900 characters, so the Risk Reviewer reviewed a StrategySpec cut off
    mid-section and never knew. A stage's output is INPUT to the next stage;
    display length must not amputate it."""
    assert orch.STAGE_LIMIT >= 10000

    seen: dict = {}

    async def ask(persona, question, who, channel, bot="director", history="",
                  limit=1900):
        seen[bot] = limit
        return "x"

    async def post(bot, label, text):
        pass

    run(orch.run_pipeline("idea", "u", "c", ask, PERSONAS, post))
    assert set(seen.values()) == {orch.STAGE_LIMIT}, \
        "every stage must request the full text, not the chat display limit"


def test_a_long_stage_reaches_the_next_stage_intact() -> None:
    """The property that matters: whatever stage N produced, stage N+1 sees."""
    long_spec = "## StrategySpec\n" + ("- a condition line\n" * 400)

    calls = {"n": 0}

    async def ask(persona, question, who, channel, bot="director", history="",
                  limit=1900):
        i = calls["n"]
        calls["n"] += 1
        if i == 1:                       # StrategySpec Mode
            return long_spec
        if i == 2:                       # Skeptical Critic Mode
            assert long_spec in question, "critic stage got a truncated spec"
        return "ok"

    async def post(bot, label, text):
        pass

    res = run(orch.run_pipeline("idea", "u", "c", ask, PERSONAS, post))
    assert res.ok


def test_stage_briefs_restate_the_critical_guardrail_placeholder() -> None:
    """Kept as a marker so the parametrised guardrail test below is not the only
    thing pinning brief content."""
    assert all(s.brief.strip() for s in orch.PIPELINE)


@pytest.mark.parametrize("stage,phrase", [
    (1, "never\nfilled with a default"),
    (2, "Falsification, not improvement"),
    (2, "Report defects. Do not fix them"),
    (3, "no backtest has run"),
])
def test_stage_briefs_restate_the_critical_guardrail(stage: int, phrase: str) -> None:
    """The brief cannot relax a persona rule, but it must not undercut one
    either - each stage is reminded of the failure mode that matters there."""
    assert phrase in orch.PIPELINE[stage].brief


def test_framing_stage_does_not_write_the_spec() -> None:
    """Intake and authoring stay separate stages even inside one agent.

    Collapsing them would let the Director frame and specify in a single pass,
    where the framing's job - naming what is UNDEFINED - gets quietly satisfied
    by filling those fields in instead."""
    assert "do not write the strategyspec yet" in orch.PIPELINE[0].brief.lower()
