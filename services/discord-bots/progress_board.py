#!/usr/bin/env python3
"""QuantForge progress board.

Renders board_state.json as a visual Discord board and edits ONE pinned message
in place, so the channel never fills with duplicate boards.

Usage:
    python progress_board.py post            # create or update the board
    python progress_board.py done B1 V2      # mark items complete, then update
    python progress_board.py undo B1         # un-mark items, then update
    python progress_board.py show            # print to stdout, no Discord call
"""
from __future__ import annotations

import json
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "board_state.json"
CFG = Path("/root/.config/quantforge")
POINTER = CFG / "board_message.json"

BAR_W = 22
OWNERS = ["Jayden", "Jaedyn", "Both"]


# ------------------------------------------------------------------ helpers

def load_env() -> dict[str, str]:
    env = {}
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
                 "User-Agent": "QuantForge-Board (local,1.0)"})
    try:
        # URL is a hardcoded https://discord.com literal, not user input.
        with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310
            return r.status, (json.load(r) if r.status != 204 else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def bar(done: int, total: int, width: int = BAR_W) -> str:
    if total == 0:
        return "─" * width
    filled = round(width * done / total)
    return "█" * filled + "░" * (width - filled)


def pct(done: int, total: int) -> int:
    return 0 if total == 0 else round(100 * done / total)


# ------------------------------------------------------------------ render

def render(state: dict) -> str:
    items = all_items(state)
    total, done = len(items), sum(i["done"] for i in items)

    due = datetime.fromisoformat(state["due"]).replace(tzinfo=UTC)
    now = datetime.now(UTC)
    left = due - now
    days, hours = left.days, left.seconds // 3600
    if left.total_seconds() < 0:
        remain = "OVERDUE"
    elif days > 0:
        remain = f"{days}d {hours}h left"
    else:
        remain = f"{hours}h left"

    L: list[str] = []
    L.append("╔" + "═" * 52 + "╗")
    L.append("║  QUANTFORGE · WEEK 1" + " " * 31 + "║")
    L.append("║  Stage 1 / Month 1 — Prove the Core Concept" + " " * 8 + "║")
    L.append("╚" + "═" * 52 + "╝")
    L.append("")
    L.append(f"  OVERALL   {bar(done, total)}  {pct(done, total):>3}%   {done}/{total} done")
    L.append(f"  DUE       Tue 8 Sep, 17:00 · {remain}")
    L.append("")

    # per-section
    L.append("  ┌─ SECTIONS " + "─" * 40)
    for s in state["sections"]:
        d = sum(i["done"] for i in s["items"])
        t = len(s["items"])
        L.append(f"  │ {s['name']:<8} {bar(d, t, 18)} {pct(d, t):>3}%  {d}/{t}")
    L.append("  └" + "─" * 51)
    L.append("")

    # per-owner workload
    L.append("  ┌─ WHO OWNS WHAT " + "─" * 35)
    for o in OWNERS:
        mine = [i for i in items if i["owner"] == o]
        if not mine:
            continue
        d, t = sum(i["done"] for i in mine), len(mine)
        L.append(f"  │ {o:<8} {bar(d, t, 18)} {pct(d, t):>3}%  {d}/{t}")
    L.append("  └" + "─" * 51)
    L.append("")

    # task list
    for s in state["sections"]:
        d = sum(i["done"] for i in s["items"])
        L.append(f"  {s['name'].upper()}  ({d}/{len(s['items'])})")
        for i in s["items"]:
            mark = "✔" if i["done"] else "·"
            wrapped = textwrap.wrap(i["text"], width=42) or [""]
            L.append(f"   {mark} [{i['id']}] {i['owner']:<7} {wrapped[0]}")
            for cont in wrapped[1:]:
                L.append(f"     {'':<12} {cont}")
        L.append("")

    out = "```\n" + "\n".join(L).rstrip() + "\n```"
    if len(out) > 2000:  # Discord hard limit; never let the board fail to post
        out = out[:1990].rsplit("\n", 1)[0] + "\n…\n```"
    return out


def embed(state: dict) -> dict:
    items = all_items(state)
    total, done = len(items), sum(i["done"] for i in items)
    p = pct(done, total)
    colour = 0x2ECC71 if p == 100 else (0xF1C40F if p >= 50 else 0xE74C3C)
    return {
        "title": "Week 1 · Stage 1 / Month 1",
        "description": state["goal"],
        "color": colour,
        "fields": [
            {"name": "Progress", "value": f"{bar(done, total, 16)} {p}%", "inline": True},
            {"name": "Tasks", "value": f"{done}/{total}", "inline": True},
            {"name": "Due", "value": "<t:1757350800:R>", "inline": True},
            {"name": "Labels",
             "value": " · ".join(f"`{x}`" for x in state["labels"]), "inline": False},
            {"name": "Artifacts due",
             "value": "\n".join(f"• {a}" for a in state["artifacts"]), "inline": False},
            {"name": "Done when", "value": state["done_when"], "inline": False},
        ],
        "footer": {"text": "Updates in place · ask a bot to mark items done"},
    }


# ------------------------------------------------------------------ actions

def load_state() -> dict:
    """Typed accessor; json.loads returns Any which defeats type inference."""
    data: dict = json.loads(STATE.read_text())
    return data


def all_items(state: dict) -> list[dict]:
    out: list[dict] = []
    for section in state["sections"]:
        out.extend(section["items"])
    return out


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
    state = load_state()
    payload = {"content": render(state), "embeds": [embed(state)]}

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
        print(render(load_state()))
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
