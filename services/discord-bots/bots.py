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
import logging
import re
import shutil
from pathlib import Path

import discord
from discord import app_commands

# ---------------------------------------------------------------- config

CFG = Path("/root/.config/quantforge")
REPO = Path("/root/projects/quantforge")
LOGDIR = REPO / "logs"
LOGDIR.mkdir(exist_ok=True)

HERMES_TIMEOUT = 180
MAX_DISCORD = 1900


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (CFG / "discord.env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
GUILD_ID = int(ENV["DISCORD_GUILD_ID"])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-18s %(levelname)-7s %(message)s",
    handlers=[logging.FileHandler(LOGDIR / "bots.log"), logging.StreamHandler()],
)
log = logging.getLogger("quantforge")

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
            log.warning("hermes timeout")
            return "That took too long to think about. Try a narrower question."
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
