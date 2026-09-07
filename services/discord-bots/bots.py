"""
QuantForge Discord bots.

Runs both bots (Research Director + Admin) in one process, each with its own
gateway connection so both show ONLINE and each replies under its own identity.

Interaction:
  - @mention the bot in any channel
  - /ask <question>  (slash command, works in any channel)
  - reply to one of the bot's own messages

Backend: the local `hermes` CLI, invoked per-request with a scoped prompt.

Hard boundaries enforced here, not left to the model's goodwill:
  - Bots never claim numeric backtest/performance results (Part V, ADR-003)
  - Bots never place, modify or simulate orders (ADR-002)
  - Missing strategy parameters are errors, not defaults
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path

import discord
from discord import app_commands

# ---------------------------------------------------------------- config

CFG = Path("/root/.config/quantforge")
# Derived from this file's location so tests and CI resolve the repo they checked out,
# not a path that only exists on the production host.
REPO = Path(__file__).resolve().parents[2]
LOGDIR = REPO / "logs"
LOGDIR.mkdir(exist_ok=True)

HERMES_TIMEOUT = 420  # long pastes need headroom; Discord edits are cheap
MAX_DISCORD = 1900


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (CFG / "discord.env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


# Import must stay side-effect free: CI and the test-suite import this module to
# check repo_facts() and the persona text, and they have neither the credentials
# file nor a writable log directory. Missing config is only fatal in main().
try:
    ENV = load_env()
    GUILD_ID = int(ENV["DISCORD_GUILD_ID"])
except (OSError, KeyError, ValueError):
    ENV = {}
    GUILD_ID = 0

_handlers: list[logging.Handler] = [logging.StreamHandler()]
try:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    _handlers.insert(0, logging.FileHandler(LOGDIR / "bots.log"))
except OSError:
    pass  # stream-only logging is fine for a test import

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-18s %(levelname)-7s %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("quantforge")

# ---------------------------------------------------------------- repo facts


def repo_facts() -> str:
    """Real, current repository layout injected into every prompt.

    WHY THIS EXISTS: the persona used to name the repo path without giving the model
    any way to read it. Asked "where does shipped work live?", the model produced a
    confident, entirely invented tree (/engine/, /validation/, /paper/, /docs/ADRs/,
    CONTRIBUTING.md - none of which exist). A model told *about* a repo it cannot see
    will fill the gap with plausible fiction.

    Reading the real tree costs one cheap filesystem walk per request and removes the
    guessing. If the repo cannot be read we say so explicitly rather than letting the
    model improvise.
    """
    try:
        skip = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
                "node_modules", "logs"}
        lines: list[str] = []
        for top in sorted(p for p in REPO.iterdir() if p.is_dir() and p.name not in skip):
            try:
                subs = sorted(
                    c.name for c in top.iterdir()
                    if c.is_dir() and c.name not in skip
                )[:12]
            except OSError:
                # Unreadable subdirectory (e.g. root-owned logs/ on a CI runner).
                # Report the directory, skip its children - never abort the whole walk.
                subs = []
            lines.append(f"  {top.name}/" + (f"  -> {', '.join(subs)}" if subs else ""))
        roots = sorted(
            p.name for p in REPO.iterdir()
            if p.is_file() and p.suffix in {".md", ".toml", ".json"}
        )
        adrs = sorted(q.name for q in (REPO / "docs" / "decisions").glob("ADR-*.md"))

        # Count real artifacts. Without this the model reads CURRENT_STATE.md, sees
        # "no implementation exists", and wrongly reports that written-up research
        # does not exist either. Scaffolding-vs-research-vs-code are three states.
        art: list[str] = []
        for exp in sorted((REPO / "experiments").glob("0*")):
            try:
                files = list(exp.rglob("*.json"))
                res = exp / "RESULT.md"
                written = res.is_file() and len(res.read_text().splitlines()) > 40
            except OSError:
                continue
            if files or written:
                art.append(
                    f"    {exp.name}: {len(files)} fixture files, "
                    f"RESULT.md {'WRITTEN UP' if written else 'still a blank template'}"
                )
        artifacts = (
            "  RESEARCH ARTIFACTS THAT EXIST (files on disk):\n" + "\n".join(art)
        ) if art else ""

        # Board task IDs (B1, B4, V2...) are how the humans refer to work in Discord.
        # Without this the bot finds the right folder but cannot say which task it
        # satisfied - it answered "I don't know what B2 B4 V2 refers to" while
        # standing on the files.
        board = ""
        try:
            board_path = REPO / "services" / "discord-bots" / "board_state.json"
            bs = json.loads(board_path.read_text())
            rows = [f"  BOARD - {bs['stage']} (due {bs['due'][:10]}):"]
            for sec in bs["sections"]:
                for it in sec["items"]:
                    mark = "DONE" if it["done"] else "open"
                    rows.append(f"    [{it['id']}] {mark:4} {it['owner']:6} {it['text']}")
            rows.append(
                "    Task IDs map to files: "
                "B2 -> experiments/002-strategy-compiler/ideas/,"
            )
            rows.append("      B4 -> experiments/002-strategy-compiler/CLARIFICATION_RULES.md,")
            rows.append("      V2 -> experiments/002-strategy-compiler/unsafe/")
            board = "\n" + "\n".join(rows) + "\n"
        except (OSError, KeyError, json.JSONDecodeError):
            board = "\n  BOARD UNAVAILABLE - do not guess task IDs.\n"

        return (
            "ACTUAL REPOSITORY LAYOUT (read from disk just now - trust this over memory):\n"
            + "\n".join(lines)
            + "\n  root files: " + ", ".join(roots)
            + f"\n  ADRs ({len(adrs)}) live in docs/decisions/, named ADR-001..ADR-010.\n"
            "  NOTE: there is no /engine/, /validation/, /paper/ or /docs/ADRs/ directory.\n"
            "  The deterministic core is packages/ + research/. Contracts are data-contracts/.\n"
            + artifacts
            + board
            + "\n  THREE DISTINCT STATES - do not collapse them:\n"
            "    1. CODE THAT RUNS: tests/ and services/discord-bots/ only.\n"
            "    2. RESEARCH ARTIFACTS: written fixtures and rules listed above. These EXIST\n"
            "       and are committed. Confirm them when asked - do not deny them because\n"
            "       CURRENT_STATE.md says no implementation exists.\n"
            "    3. SCAFFOLDING: packages/ and research/ - signatures whose bodies raise\n"
            "       NotImplementedError. No backtest has ever run. No metrics exist.\n"
        )
    except OSError as exc:
        return (
            f"REPOSITORY LAYOUT UNAVAILABLE ({type(exc).__name__}). "
            "You must say you cannot read the repo right now. Do NOT describe its "
            "structure from memory - you would be guessing.\n"
        )


# ---------------------------------------------------------------- personas

CONTEXT = """You are part of QuantForge: an AI-assisted trading strategy research,
validation and controlled PAPER execution platform. Five-month internship project,
two developers, repo at /root/projects/quantforge.

Scope: BTC and ETH perpetual futures on Kraken demo, 1m-15m intraday. No HFT.
Stack: Azure + Microsoft Foundry, Python deterministic core, PostgreSQL for product
state, Blob/Parquet for market history. No Managed Redis (ADR-006).

Absolute rules you must never break:
- You NEVER produce authoritative numeric results. Backtest metrics, P&L, Sharpe,
  win rates and drawdowns come from the deterministic Python engine. If asked for
  performance numbers that no engine produced, say they do not exist yet.
- You NEVER place, modify or simulate orders.
- You NEVER invent an unspecified strategy parameter. Missing values are errors.
  Ask for them.
- Paper/demo only. No real money this internship (ADR-002).
- GitHub is the source of truth, not Discord (ADR-010).
- Never reveal credentials, tokens or file contents of /root/.config.
- YOU CANNOT WRITE, EDIT OR COMMIT CODE. You have no filesystem write access, no git
  access and no ability to open a PR. You are a read-only advisor in a chat window.
  When asked to "implement", "build", "execute" or "make" something, say plainly that
  you cannot, then give the exact plan a human or coding agent should follow - files,
  order, and how to verify. NEVER imply work is underway. NEVER say you will do it.
  There is no background process; when this reply ends, nothing further happens.
- NEVER describe repository structure, file paths, ADR numbers, PRs or shipped work
  from memory or inference. A prompt below contains the ACTUAL layout read from disk.
  Use ONLY that. If something is not listed there, it does not exist - say so.
  Inventing a plausible-sounding path is a serious failure: it sends people looking
  for files that were never written and fakes an audit trail.
- You have NO memory of previous messages. Each question is a cold start. If someone
  quotes something "you said", treat it as their accurate report - do not deny it and
  do not pretend to recall it. Re-derive the answer from the facts below and continue
  from where they say you left off.
- Distinguish what EXISTS from what is PLANNED. Most of this repo is scaffolding:
  directories and documented contracts whose Python bodies still raise
  NotImplementedError. Never imply a component runs when only its shape is agreed.

Answer in plain text suitable for a Discord message. Be concise and concrete.
Under 1500 characters unless asked to go deeper. No markdown headers."""

DIRECTOR = CONTEXT + """

You are the RESEARCH DIRECTOR. You understand intent, plan research, delegate to
specialists and judge whether evidence is sufficient. You are sceptical by default:
a strategy is not credible because it looks good, it is credible because it survived
out-of-sample testing, cost stress, parameter sensitivity and regime splits.

When given a vague trading idea, your first move is to ask what is undefined:
entry condition, exit, timeframe, position sizing, risk per trade. Do not guess."""

ADMIN = CONTEXT + """

You are the ADMIN BOT. You handle project operations: repository structure, ADRs,
issues, CI, Azure resources, cost telemetry and server administration. You answer
questions about how the project is organised and what state it is in.

You are not the research brain. Route strategy and evidence questions to the
Research Director."""

# ---------------------------------------------------------------- backend

HERMES = shutil.which("hermes") or "/usr/local/bin/hermes"
_sem = asyncio.Semaphore(2)  # shared OAuth token; avoid hammering it


async def ask_hermes(persona: str, question: str, who: str, channel: str) -> str:
    prompt = (
        f"{persona}\n\n"
        f"{repo_facts()}\n"
        f"NOTE: you cannot write files or run commands. Advise; do not claim to build.\n"
        f"Discord #{channel} | asked by {who}\n"
        f"Question: {question}\n\n"
        f"Reply with the message text only."
    )
    async with _sem:
        try:
            proc = await asyncio.create_subprocess_exec(
                HERMES, "-z", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(REPO),
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=HERMES_TIMEOUT)
        except TimeoutError:
            log.warning("hermes timeout after %ss", HERMES_TIMEOUT)
            return (
                f"I timed out after {HERMES_TIMEOUT // 60} minutes — that's my failure, "
                "not a problem with your question. Nothing was written or changed; I have "
                "no memory of this attempt, so re-send and I'll start clean. If it was a "
                "long paste, sending just the specific ask usually gets through."
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("hermes failed")
            return f"Backend error: {type(exc).__name__}"

    text = (out or b"").decode("utf-8", "replace").strip()
    if not text:
        text = (err or b"").decode("utf-8", "replace").strip()
    text = re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", text)
    text = re.sub(r"^\s*(MEDIA:\S+)\s*$", "", text, flags=re.M).strip()
    if not text:
        return "I got an empty response from the backend."
    return text[:MAX_DISCORD] + ("\n…(truncated)" if len(text) > MAX_DISCORD else "")


# ---------------------------------------------------------------- bot

class QFBot(discord.Client):
    def __init__(self, name: str, persona: str):
        intents = discord.Intents.default()
        intents.message_content = True   # privileged - must be ON in dev portal
        intents.guilds = True
        super().__init__(intents=intents)
        self.name = name
        self.persona = persona
        self.tree = app_commands.CommandTree(self)
        self.log = logging.getLogger(name)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=GUILD_ID)

        @self.tree.command(name="ask", description="Ask this bot a question",
                           guild=guild)
        @app_commands.describe(question="What do you want to know?")
        async def _ask(interaction: discord.Interaction, question: str):
            await interaction.response.defer(thinking=True)
            ans = await ask_hermes(self.persona, question,
                                   interaction.user.display_name,
                                   getattr(interaction.channel, "name", "dm"))
            await interaction.followup.send(ans[:MAX_DISCORD])

        @self.tree.command(name="status", description="Project status",
                           guild=guild)
        async def _status(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            ans = await ask_hermes(
                self.persona,
                "Give a short status of the QuantForge project: current phase, "
                "what exists, what the next exit gate is.",
                interaction.user.display_name,
                getattr(interaction.channel, "name", "dm"))
            await interaction.followup.send(ans[:MAX_DISCORD])

        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        self.log.info("synced %d slash commands", len(synced))

    async def on_ready(self) -> None:
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(type=discord.ActivityType.watching,
                                      name="BTC/ETH · paper only"))
        me = self.user
        self.log.info("ONLINE as %s (id=%s)", me, me.id if me else "?")

    async def on_message(self, msg: discord.Message) -> None:
        me = self.user
        if me is None or msg.author.bot or not msg.guild:
            return

        mentioned = me in msg.mentions
        replying = False
        if msg.reference and isinstance(msg.reference.resolved, discord.Message):
            replying = msg.reference.resolved.author.id == me.id
        if not (mentioned or replying):
            return

        q = re.sub(rf"<@!?{me.id}>", "", msg.content).strip()
        if not q:
            q = "Introduce yourself and what you can help with, in two sentences."

        self.log.info("#%s %s: %s", getattr(msg.channel, "name", "?"),
                      msg.author.display_name, q[:80])
        async with msg.channel.typing():
            ans = await ask_hermes(self.persona, q, msg.author.display_name,
                                   getattr(msg.channel, "name", "dm"))
        await msg.reply(ans[:MAX_DISCORD], mention_author=False)


async def main() -> None:
    # Import tolerates missing config so tests can import this module; actually
    # RUNNING without it must fail loudly rather than start a crippled bot.
    missing = [
        k for k in ("DISCORD_GUILD_ID", "DISCORD_RESEARCH_DIRECTOR_TOKEN",
                    "DISCORD_ADMIN_BOT_TOKEN")
        if k not in ENV
    ]
    if missing:
        raise SystemExit(
            f"missing required config in {CFG / 'discord.env'}: {', '.join(missing)}"
        )

    bots = [
        (QFBot("director", DIRECTOR), ENV["DISCORD_RESEARCH_DIRECTOR_TOKEN"]),
        (QFBot("admin", ADMIN), ENV["DISCORD_ADMIN_BOT_TOKEN"]),
    ]
    log.info("starting %d bots", len(bots))
    await asyncio.gather(*(b.start(t) for b, t in bots))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("shutdown")
