#!/usr/bin/env python3
"""QuantForge progress board.

Renders board_state.json as a Discord *embed* and edits ONE pinned message in
place, so the channel never fills with duplicate boards.

Design notes:
  - Bars live inside inline code spans. Discord renders embed field values in a
    proportional font, so `█░` and label padding only align inside monospace.
  - Fenced ``` blocks are reserved for StrategySpec/code references (per spec).
  - Sections are separate full-width fields (inline=False), not one text blob.

Usage:
    python progress_board.py post            # create or update the board
    python progress_board.py done B1 V2      # mark items complete, then update
    python progress_board.py undo B1         # un-mark items, then update
    python progress_board.py show            # print embed JSON, no Discord call
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "board_state.json"
CFG = Path("/root/.config/quantforge")
POINTER = CFG / "board_message.json"

# --- visual language ----------------------------------------------------
BAR_W = 16          # 15-20 char budget
LABEL_W = 7         # monospace label padding
FILLED, EMPTY = "█", "░"

COLOR_PROGRESS = 0x5865F2   # blurple - in progress
COLOR_COMPLETE = 0x57F287   # green   - complete
COLOR_PRIORITY = 0xEB459E   # pink    - priority / at risk

E_PROGRESS, E_DONE, E_BUILD, E_VERIFY = "📊", "✅", "🏗️", "✔️"
E_OWNER, E_ART, E_TARGET = "👤", "📦", "🎯"

# Discord hard limits
MAX_EMBED_TOTAL = 6000
MAX_FIELD_VALUE = 1024
MAX_FIELDS = 25

OWNERS = ["Jayden", "Jaedyn", "Both"]


# ------------------------------------------------------------------ helpers

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (CFG / "discord.env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def api(method: str, path: str, token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"https://discord.com/api/v10{path}", data=data, method=method,
        headers={"Authorization": f"Bot {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "QuantForge-Board (local,2.0)"})
    try:
        # URL is a hardcoded https://discord.com literal, not user input.
        with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310
            return r.status, (json.load(r) if r.status != 204 else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def load_state() -> dict:
    """Typed accessor; json.loads returns Any which defeats type inference."""
    data: dict = json.loads(STATE.read_text())
    return data


def all_items(state: dict) -> list[dict]:
    out: list[dict] = []
    for section in state["sections"]:
        out.extend(section["items"])
    return out


def bar(done: int, total: int, width: int = BAR_W) -> str:
    if total == 0:
        return EMPTY * width
    filled = round(width * done / total)
    return FILLED * filled + EMPTY * (width - filled)


def pct(done: int, total: int) -> int:
    return 0 if total == 0 else round(100 * done / total)


def meter(label: str, done: int, total: int, width: int = BAR_W) -> str:
    """One aligned monospace row: `Label  : ███░░░  60%  3/5`.

    Labels longer than LABEL_W are truncated rather than pushing the bar out
    of alignment with the other rows.
    """
    return (f"`{label[:LABEL_W]:<{LABEL_W}}: {bar(done, total, width)} "
            f"{pct(done, total):>3}%  {done}/{total}`")


def tally(items: list[dict]) -> tuple[int, int]:
    return sum(bool(i["done"]) for i in items), len(items)


def clamp(value: str, limit: int = MAX_FIELD_VALUE) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 2].rsplit("\n", 1)[0] + "\n…"


# ------------------------------------------------------------------ render

def due_stamp(state: dict) -> tuple[int, str]:
    due = datetime.fromisoformat(state["due"]).replace(tzinfo=UTC)
    left = due - datetime.now(UTC)
    if left.total_seconds() < 0:
        return int(due.timestamp()), "OVERDUE"
    days, hours = left.days, left.seconds // 3600
    return int(due.timestamp()), (f"{days}d {hours}h left" if days else f"{hours}h left")


def section_field(section: dict) -> dict:
    """One field per section, tasks grouped by assignee."""
    done, total = tally(section["items"])
    icon = E_BUILD if section["name"].lower() == "build" else E_VERIFY

    lines = [meter("tasks", done, total), ""]
    for owner in OWNERS:
        mine = [i for i in section["items"] if i["owner"] == owner]
        if not mine:
            continue
        lines.append(f"**{owner}**")
        for i in mine:
            mark = E_DONE if i["done"] else "▫️"
            text = f"~~{i['text']}~~" if i["done"] else i["text"]
            lines.append(f"{mark} `[{i['id']}]` {text}")
        lines.append("")

    return {
        "name": f"{icon} **[{section['name'].upper()}]**  ·  {done}/{total}",
        "value": clamp("\n".join(lines).rstrip()),
        "inline": False,
    }


def build_embed(state: dict) -> dict:
    items = all_items(state)
    done, total = tally(items)
    p = pct(done, total)
    ts, remaining = due_stamp(state)

    if p == 100:
        colour = COLOR_COMPLETE
    elif remaining == "OVERDUE":
        colour = COLOR_PRIORITY
    else:
        colour = COLOR_PROGRESS

    fields: list[dict] = [
        {
            "name": f"{E_PROGRESS} **Overall**",
            "value": (f"{meter('overall', done, total)}\n"
                      f"-# Due <t:{ts}:F> · <t:{ts}:R> · {remaining}"),
            "inline": False,
        },
        {
            "name": f"{E_OWNER} **[WHO OWNS WHAT]**",
            "value": "\n".join(
                meter(o, *tally([i for i in items if i["owner"] == o]))
                for o in OWNERS if any(i["owner"] == o for i in items)),
            "inline": False,
        },
    ]

    fields.extend(section_field(s) for s in state["sections"])

    fields.append({
        "name": f"{E_ART} **Artifacts due**",
        "value": clamp("\n".join(f"▫️ {a}" for a in state["artifacts"])),
        "inline": False,
    })
    fields.append({
        "name": f"{E_TARGET} **Done when**",
        "value": clamp(f"-# {state['done_when']}"),
        "inline": False,
    })

    embed = {
        "title": f"QuantForge · {state['stage']}",
        "description": (f"{state['goal']}\n\n"
                        + " ".join(f"`{x}`" for x in state["labels"])),
        "color": colour,
        "fields": fields[:MAX_FIELDS],
        "footer": {"text": f"{p}% complete · {done}/{total} tasks · "
                           f"due Tue 8 Sep 17:00 · updated"},
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return enforce_limits(embed)


def embed_size(embed: dict) -> int:
    n = len(embed.get("title", "")) + len(embed.get("description", ""))
    n += len(embed.get("footer", {}).get("text", ""))
    for f in embed.get("fields", []):
        n += len(f["name"]) + len(f["value"])
    return n


def enforce_limits(embed: dict) -> dict:
    """Discord rejects the whole message if any limit is exceeded."""
    for f in embed["fields"]:
        f["value"] = clamp(f["value"])
    while embed_size(embed) > MAX_EMBED_TOTAL and len(embed["fields"]) > 1:
        embed["fields"].pop()
        embed["fields"][-1]["value"] = clamp(
            embed["fields"][-1]["value"] + "\n-# …truncated to fit Discord limits")
    return embed


# ------------------------------------------------------------------ actions

def set_done(ids: list[str], value: bool) -> list[str]:
    state = load_state()
    changed: list[str] = []
    wanted = {i.upper() for i in ids}
    for item in all_items(state):
        if str(item["id"]).upper() in wanted and item["done"] != value:
            item["done"] = value
            changed.append(str(item["id"]))
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    return changed


def publish(channel_id: str, token: str) -> tuple[int, str]:
    payload = {"content": "", "embeds": [build_embed(load_state())]}

    if POINTER.exists():
        ptr = json.loads(POINTER.read_text())
        st, _ = api("PATCH",
                    f"/channels/{ptr['channel_id']}/messages/{ptr['message_id']}",
                    token, payload)
        if st == 200:
            return st, f"edited existing board {ptr['message_id']}"

    st, msg = api("POST", f"/channels/{channel_id}/messages", token, payload)
    if st in (200, 201) and isinstance(msg, dict):
        message_id = str(msg["id"])
        POINTER.write_text(json.dumps(
            {"channel_id": channel_id, "message_id": message_id}, indent=2))
        api("PUT", f"/channels/{channel_id}/pins/{message_id}", token)
        return st, f"created and pinned board {message_id}"
    return st, str(msg)


def main() -> int:
    args = sys.argv[1:] or ["show"]
    cmd, rest = args[0], args[1:]

    if cmd == "show":
        e = build_embed(load_state())
        print(json.dumps(e, indent=2, ensure_ascii=False))
        print(f"\n-- {embed_size(e)} chars / {MAX_EMBED_TOTAL}, "
              f"{len(e['fields'])} fields --", file=sys.stderr)
        return 0

    env = load_env()
    token = env["DISCORD_ADMIN_BOT_TOKEN"]
    channel = env.get("DISCORD_BOARD_CHANNEL_ID")
    if not channel:
        print("DISCORD_BOARD_CHANNEL_ID missing from discord.env", file=sys.stderr)
        return 2

    if cmd in ("done", "undo"):
        changed = set_done(rest, cmd == "done")
        print(f"{cmd}: {changed or 'nothing changed'}")

    st, info = publish(channel, token)
    print(f"HTTP {st} — {info}")
    return 0 if st in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())
