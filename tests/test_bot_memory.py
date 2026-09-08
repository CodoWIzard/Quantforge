"""Behavioural tests for conversation memory (bots.recent_context).

Each reply is a fresh `hermes -z` process with no state, so the bot's only
memory is the channel transcript this function builds. These tests drive it with
a fake channel rather than asserting on source text: the ordering, the speaker
labels and the failure mode are the things that actually break the answer.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

BOTS_DIR = Path(__file__).resolve().parents[1] / "services" / "discord-bots"
sys.path.insert(0, str(BOTS_DIR))

discord = pytest.importorskip("discord")
import bots  # noqa: E402


class FakeAuthor:
    def __init__(self, uid: int, name: str, bot: bool = False):
        self.id, self.display_name, self.bot = uid, name, bot


class FakeMessage:
    def __init__(self, mid: int, author: FakeAuthor, content: str):
        self.id, self.author, self.clean_content = mid, author, content


class FakeChannel(discord.abc.Messageable):
    """Newest-first history, exactly like discord.py."""

    def __init__(self, msgs: list[FakeMessage], error: Exception | None = None):
        self._msgs, self._error = msgs, error

    async def _get_channel(self):  # required by Messageable
        return self

    def history(self, limit: int = 100):
        error, msgs = self._error, list(reversed(self._msgs))[:limit]

        async def gen():
            if error:
                raise error
            for m in msgs:
                yield m
        return gen()


ME = FakeAuthor(1, "Research_Director", bot=True)
OTHER_BOT = FakeAuthor(2, "Admin-bot", bot=True)
HUMAN = FakeAuthor(3, "JaydenInfra")


def ctx(msgs, me=ME, skip=None) -> str:
    return asyncio.run(bots.recent_context(FakeChannel(msgs), me, skip_id=skip))


def test_transcript_is_chronological() -> None:
    """Discord returns newest-first; a reversed transcript inverts cause and effect."""
    out = ctx([
        FakeMessage(10, HUMAN, "first question"),
        FakeMessage(11, ME, "first answer"),
        FakeMessage(12, HUMAN, "follow up"),
    ])
    assert out.index("first question") < out.index("first answer") < out.index("follow up")


def test_own_replies_are_labelled_YOU() -> None:
    """The model must recognise its own past answers to build on them."""
    out = ctx([FakeMessage(10, ME, "B3 has landed")])
    assert "YOU: B3 has landed" in out


def test_the_other_bot_is_labelled_as_such() -> None:
    """Two bots share the channel. Mistaking Admin's words for its own makes the
    Director claim work it never did."""
    out = ctx([FakeMessage(10, OTHER_BOT, "CI is green")])
    assert "Admin-bot (the other bot): CI is green" in out
    assert "YOU:" not in out


def test_humans_are_named() -> None:
    assert "JaydenInfra: ship it" in ctx([FakeMessage(10, HUMAN, "ship it")])


def test_current_message_is_skipped() -> None:
    """It is passed separately as the question; twice invites the model to answer
    the echo instead of the ask."""
    out = ctx([FakeMessage(10, HUMAN, "older"), FakeMessage(11, HUMAN, "asking now")],
              skip=11)
    assert "older" in out and "asking now" not in out


def test_empty_channel_yields_no_transcript_block() -> None:
    """An empty 'here is the conversation' header would imply nothing was said."""
    assert ctx([]) == ""


def test_unreadable_history_degrades_instead_of_raising() -> None:
    """Missing Read Message History permission must not kill the reply."""
    chan = FakeChannel([FakeMessage(10, HUMAN, "hi")],
                       error=discord.DiscordException("missing permissions"))
    assert asyncio.run(bots.recent_context(chan, ME)) == ""


def test_non_messageable_channel_is_handled() -> None:
    assert asyncio.run(bots.recent_context(object(), ME)) == ""


def test_long_pastes_are_truncated_per_message() -> None:
    """One 9KB paste must not crowd the repo facts out of the prompt."""
    out = ctx([FakeMessage(10, HUMAN, "x" * 5000)])
    assert "…[truncated]" in out
    assert len(out) < 2000


def test_total_transcript_is_budgeted() -> None:
    msgs = [FakeMessage(i, HUMAN, "y" * 600) for i in range(bots.HISTORY_LIMIT)]
    assert len(ctx(msgs)) < bots.HISTORY_BUDGET * 2


def test_transcript_tells_the_model_files_outrank_its_past_answers() -> None:
    """Otherwise it defends a stale claim after the repo moved on."""
    out = ctx([FakeMessage(10, ME, "no compiler exists")])
    assert "the files win" in out


def test_empty_message_still_appears_as_a_turn() -> None:
    """An image-only message is still a turn; dropping it silently desyncs the
    transcript from what the human sees on screen."""
    assert "[attachment or embed]" in ctx([FakeMessage(10, HUMAN, "   ")])
