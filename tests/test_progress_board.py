"""Contract tests for the progress board embed renderer."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "discord-bots"))

import progress_board as pb  # noqa: E402


@pytest.fixture
def state() -> dict:
    return json.loads((ROOT / "services" / "discord-bots" / "board_state.json").read_text())


# --- Discord API limits -------------------------------------------------

def test_embed_within_total_character_limit(state: dict) -> None:
    """Discord rejects the whole message if the embed exceeds 6000 chars."""
    assert pb.embed_size(pb.build_embed(state)) <= pb.MAX_EMBED_TOTAL


def test_no_field_value_exceeds_1024(state: dict) -> None:
    for f in pb.build_embed(state)["fields"]:
        assert len(f["value"]) <= pb.MAX_FIELD_VALUE, f["name"]


def test_field_count_within_limit(state: dict) -> None:
    assert len(pb.build_embed(state)["fields"]) <= pb.MAX_FIELDS


def test_oversized_board_degrades_instead_of_failing(state: dict) -> None:
    """A growing board must still post, truncated, never raise or 400."""
    state["sections"][0]["items"] *= 60
    e = pb.build_embed(state)
    assert pb.embed_size(e) <= pb.MAX_EMBED_TOTAL
    assert all(len(f["value"]) <= pb.MAX_FIELD_VALUE for f in e["fields"])


def test_embed_is_json_serialisable(state: dict) -> None:
    json.dumps(pb.build_embed(state))


# --- colour coding ------------------------------------------------------

def test_colour_blurple_while_in_progress(state: dict) -> None:
    for i in pb.all_items(state):
        i["done"] = False
    assert pb.build_embed(state)["color"] == pb.COLOR_PROGRESS


def test_colour_green_when_complete(state: dict) -> None:
    for i in pb.all_items(state):
        i["done"] = True
    assert pb.build_embed(state)["color"] == pb.COLOR_COMPLETE


def test_colour_pink_when_overdue(state: dict) -> None:
    state["due"] = "2020-01-01T00:00:00"
    assert pb.build_embed(state)["color"] == pb.COLOR_PRIORITY


# --- visual contract ----------------------------------------------------

def test_bars_within_width_budget() -> None:
    """Spec: 15-20 characters."""
    assert 15 <= pb.BAR_W <= 20
    for d in range(9):
        assert len(pb.bar(d, 8)) == pb.BAR_W


def test_meter_is_monospace_and_aligned() -> None:
    """Bars only align inside code spans; label padding must be uniform."""
    rows = [pb.meter("Jayden", 1, 3), pb.meter("Both", 0, 2)]
    for r in rows:
        assert r.startswith("`") and r.endswith("`")
    assert len({r.index(":") for r in rows}) == 1


def test_all_meters_share_one_column_grid(state: dict) -> None:
    """Every bar across every field must start at the same column."""
    e = pb.build_embed(state)
    rows = [ln for f in e["fields"] for ln in f["value"].split("\n")
            if ln.startswith("`") and ":" in ln and ("\u2588" in ln or "\u2591" in ln)]
    assert len(rows) >= 5
    assert len({r.index(":") for r in rows}) == 1, "bar start columns differ"
    assert len({len(r) for r in rows}) == 1, "meter rows differ in length"


def test_long_label_truncates_instead_of_breaking_grid() -> None:
    a = pb.meter("x" * 40, 1, 2)
    b = pb.meter("ok", 1, 2)
    assert len(a) == len(b)


def test_sections_are_full_width(state: dict) -> None:
    for f in pb.build_embed(state)["fields"]:
        assert f["inline"] is False


def test_section_headers_are_bold_bracketed(state: dict) -> None:
    names = [f["name"] for f in pb.build_embed(state)["fields"]]
    assert any("**[BUILD]**" in n for n in names)
    assert any("**[VERIFY]**" in n for n in names)
    assert any("**[WHO OWNS WHAT]**" in n for n in names)


def test_task_ids_in_inline_code(state: dict) -> None:
    blob = "\n".join(f["value"] for f in pb.build_embed(state)["fields"])
    for i in pb.all_items(state):
        assert f"`[{i['id']}]`" in blob


def test_assignees_are_bold(state: dict) -> None:
    blob = "\n".join(f["value"] for f in pb.build_embed(state)["fields"])
    for owner in ("Jayden", "Jaedyn"):
        assert f"**{owner}**" in blob


def test_no_fenced_code_blocks(state: dict) -> None:
    """Fences are reserved for StrategySpec references, not layout."""
    e = pb.build_embed(state)
    blob = e["description"] + "".join(f["value"] for f in e["fields"])
    assert "```" not in blob


def test_footer_has_completion_and_due(state: dict) -> None:
    footer = pb.build_embed(state)["footer"]["text"]
    assert "%" in footer and "due" in footer.lower()


def test_has_update_timestamp(state: dict) -> None:
    assert "timestamp" in pb.build_embed(state)


def test_due_date_uses_discord_timestamp_markup(state: dict) -> None:
    blob = "".join(f["value"] for f in pb.build_embed(state)["fields"])
    assert re.search(r"<t:\d+:[FR]>", blob)


# --- data integrity -----------------------------------------------------

def test_all_items_flattens_sections(state: dict) -> None:
    assert len(pb.all_items(state)) == sum(len(s["items"]) for s in state["sections"])


def test_every_item_has_owner_and_id(state: dict) -> None:
    for i in pb.all_items(state):
        assert i["id"] and i["owner"] and i["text"]
        assert i["owner"] in ("Jayden", "Jaedyn", "Both")


def test_ids_are_unique(state: dict) -> None:
    ids = [i["id"] for i in pb.all_items(state)]
    assert len(ids) == len(set(ids))


def test_every_task_appears_in_embed(state: dict) -> None:
    blob = "\n".join(f["value"] for f in pb.build_embed(state)["fields"])
    for i in pb.all_items(state):
        assert f"`[{i['id']}]`" in blob


@pytest.mark.parametrize("done,total,want", [(0, 8, 0), (4, 8, 50), (8, 8, 100), (0, 0, 0)])
def test_pct(done: int, total: int, want: int) -> None:
    assert pb.pct(done, total) == want


def test_completed_tasks_are_struck_through(state: dict) -> None:
    state["sections"][0]["items"][0]["done"] = True
    blob = "\n".join(f["value"] for f in pb.build_embed(state)["fields"])
    assert "~~" in blob


def test_board_does_not_leak_tokens(state: dict) -> None:
    assert not re.search(r"MTU[0-9A-Za-z._-]{50,}", json.dumps(pb.build_embed(state)))
