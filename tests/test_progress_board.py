"""Contract tests for the progress board renderer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "discord-bots"))

import progress_board as pb  # noqa: E402


@pytest.fixture
def state() -> dict:
    return json.loads((ROOT / "services" / "discord-bots" / "board_state.json").read_text())


def test_renders_under_discord_2000_char_limit(state: dict) -> None:
    """Discord rejects content over 2000 chars with HTTP 400."""
    assert len(pb.render(state)) <= 2000


def test_render_truncates_rather_than_overflowing() -> None:
    """A board that grows must degrade gracefully, never fail to post."""
    big = json.loads((ROOT / "services" / "discord-bots" / "board_state.json").read_text())
    big["sections"][0]["items"] *= 40
    assert len(pb.render(big)) <= 2000


def test_all_items_flattens_sections(state: dict) -> None:
    assert len(pb.all_items(state)) == sum(len(s["items"]) for s in state["sections"])


def test_every_item_has_owner_and_id(state: dict) -> None:
    for i in pb.all_items(state):
        assert i["id"] and i["owner"] and i["text"]
        assert i["owner"] in ("Jayden", "Jaedyn", "Both")


def test_ids_are_unique(state: dict) -> None:
    ids = [i["id"] for i in pb.all_items(state)]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("done,total,want", [(0, 8, 0), (4, 8, 50), (8, 8, 100), (0, 0, 0)])
def test_pct(done: int, total: int, want: int) -> None:
    assert pb.pct(done, total) == want


def test_bar_width_is_constant() -> None:
    for d in range(9):
        assert len(pb.bar(d, 8, 20)) == 20


def test_embed_colour_reflects_progress(state: dict) -> None:
    for i in pb.all_items(state):
        i["done"] = False
    assert pb.embed(state)["color"] == 0xE74C3C
    for i in pb.all_items(state):
        i["done"] = True
    assert pb.embed(state)["color"] == 0x2ECC71


def test_board_does_not_leak_tokens(state: dict) -> None:
    import re
    assert not re.search(r"MTU[0-9A-Za-z._-]{50,}", pb.render(state))
