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

import builder
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
# Conversation memory: how far back to read the channel. 25 messages covers a
# working exchange without dragging in yesterday's unrelated thread, and the
# character budget stops one giant paste from crowding out the repo facts.
HISTORY_LIMIT = 25
HISTORY_BUDGET = 6000


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
        # Implementation state, measured per module. NEVER hardcode this sentence:
        # when B3 landed, the old fixed text kept calling strategy_schema "scaffolding"
        # and the bot denied committed, working code existed.
        impl: list[str] = []
        for pkg_root in ("packages", "research"):
            for mod in sorted((REPO / pkg_root).glob("*/")):
                if not mod.is_dir() or mod.name.startswith((".", "_")):
                    continue
                try:
                    srcs = [p for p in mod.glob("*.py") if p.name != "__init__.py"]
                    if not srcs:
                        continue
                    text = "\n".join(p.read_text() for p in srcs)
                except OSError:
                    continue
                stubs = text.count("raise NotImplementedError")
                defs = sum(1 for line in text.splitlines()
                           if line.lstrip().startswith("def "))
                if defs == 0:
                    continue
                if stubs == 0:
                    state = "IMPLEMENTED (no stubs left)"
                elif stubs >= defs:
                    state = "SCAFFOLDING (every body is a stub)"
                else:
                    state = f"PARTIAL ({stubs} of {defs} still stubs)"
                impl.append(f"    {pkg_root}/{mod.name}: {state}")
        implementation = ("\n  IMPLEMENTATION STATE (counted from source just now):\n"
                          + "\n".join(impl) + "\n") if impl else ""

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
            + implementation
            + board
            + "\n  THREE DISTINCT STATES - do not collapse them:\n"
            "    1. CODE THAT RUNS: tests/ and services/discord-bots/ only.\n"
            "    2. RESEARCH ARTIFACTS: written fixtures and rules listed above. These EXIST\n"
            "       and are committed. Confirm them when asked - do not deny them because\n"
            "       CURRENT_STATE.md says no implementation exists.\n"
            "    3. SCAFFOLDING: modules marked SCAFFOLDING or PARTIAL above. Do NOT\n"
            "       call a module scaffolding if the scan says IMPLEMENTED - that scan\n"
            "       is counted from source and outranks any doc, including\n"
            "       CURRENT_STATE.md, which can lag behind a merge.\n"
            "  Implemented code existing does NOT mean it has been exercised: no backtest\n"
            "  has ever run and no performance metric exists anywhere in this project.\n"
        )
    except OSError as exc:
        return (
            f"REPOSITORY LAYOUT UNAVAILABLE ({type(exc).__name__}). "
            "You must say you cannot read the repo right now. Do NOT describe its "
            "structure from memory - you would be guessing.\n"
        )


async def recent_context(channel: object, me: object,
                         skip_id: int | None = None) -> str:
    """The last few messages of this channel, as a transcript.

    WHY THIS EXISTS: each reply is a fresh `hermes -z` process, so the model has
    no state of its own. Without this the bot answered "I have no memory between
    messages" to a user who had just spent five messages building up context -
    technically true of the process, useless to the human.

    Discord itself is the memory. Reading the channel back beats resuming a
    stored session: it survives restarts, it cannot drift from what the user can
    see on screen, and both bots read the same thread so neither invents a
    version of the conversation the other did not have.

    Best-effort by design. No history (DM, missing permission, API hiccup) means
    a degraded answer, never a failed one.
    """
    if not isinstance(channel, discord.abc.Messageable):
        return ""
    try:
        msgs = [m async for m in channel.history(limit=HISTORY_LIMIT)]
    except (discord.DiscordException, OSError):
        log.warning("could not read channel history", exc_info=True)
        return ""

    lines: list[str] = []
    for m in msgs:  # newest first
        if skip_id is not None and m.id == skip_id:
            continue
        text = m.clean_content.strip()
        if not text:
            text = "[attachment or embed]"
        if len(text) > 700:
            text = text[:700] + " …[truncated]"
        if me is not None and m.author.id == getattr(me, "id", None):
            who = "YOU"
        elif m.author.bot:
            who = f"{m.author.display_name} (the other bot)"
        else:
            who = m.author.display_name
        lines.append(f"{who}: {text}")
        if sum(len(x) for x in lines) > HISTORY_BUDGET:
            break

    if not lines:
        return ""
    lines.reverse()  # chronological
    return (
        "RECENT CONVERSATION IN THIS CHANNEL (oldest first, read from Discord "
        "just now - this is your memory of what was said):\n"
        + "\n".join(lines)
        + "\n\nUse it: follow up on what was already discussed, do not re-introduce\n"
          "yourself, and do not ask for something already given above. Lines marked\n"
          "YOU are your own earlier replies - own them. If an earlier reply of yours\n"
          "is contradicted by the repo files you can read now, the files win: say so\n"
          "plainly and correct it rather than defending the old answer.\n"
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
- IN THIS CHAT YOU CAN READ CODE BUT NOT WRITE IT. You are in a scratch checkout of
  the repository with read tools. Open files and quote them - that is expected and
  much better than guessing. Anything you write here is thrown away when the reply
  ends, so never claim to have changed, committed or pushed anything from chat, and
  never describe a file you edited here as if it landed in the repo.
- To actually change code there is exactly one route: the /build slash command,
  which runs you on your own branch and opens a pull request for human review.
  When asked to "implement", "build" or "make" something in chat, say plainly that
  chat cannot write, and tell them to run /build with the task.
  NEVER imply work is underway, and NEVER say you will do it yourself later.
  There is no background process; when this reply ends, nothing further happens.
- NEVER describe repository structure, file paths, ADR numbers, PRs or shipped work
  from memory or inference. A prompt below contains the ACTUAL layout read from disk,
  and you can read the files themselves. Use ONLY those. If something is in neither,
  it does not exist - say so. Inventing a plausible-sounding path is a serious
  failure: it sends people looking for files that were never written and fakes an
  audit trail.
- You CAN see the recent conversation: the last messages of this channel are read
  from Discord and included below. Treat that transcript as your memory and continue
  the thread naturally. NEVER tell anyone you have no memory between messages or that
  each question is a cold start - that is a statement about your plumbing, not an
  answer, and it is wrong now.
  Two honest limits remain, and you state THOSE instead when they bite: you see only
  the recent window, so anything older than the transcript is genuinely gone and you
  should ask them to re-paste it; and if the transcript is missing entirely you must
  say you cannot see the history right now rather than guess at what was said.
  If someone quotes something "you said" that is not in the transcript, treat it as
  their accurate report - do not deny it and do not pretend to recall it.
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
entry condition, exit, timeframe, position sizing, risk per trade. Do not guess.

In /build you own the research side of the tree: research/, experiments/,
packages/strategy_schema/, packages/exchange_contracts/, data-contracts/, tests/
and docs/. Infrastructure, CI and the bot service belong to the Admin bot - if a
task needs those, say so and let Admin build it. A build that strays outside your
scope is opened as a draft PR and flagged, so stay inside it."""

ADMIN = CONTEXT + """

You are the ADMIN BOT. You handle project operations: repository structure, ADRs,
issues, CI, Azure resources, cost telemetry and server administration. You answer
questions about how the project is organised and what state it is in.

You are not the research brain. Route strategy and evidence questions to the
Research Director.

In /build you own the operational side of the tree: services/, scripts/, infra/,
.github/, packages/risk_engine/, tests/, docs/ and the dependency manifests.
Strategy code, research and experiments belong to the Research Director - if a
task needs those, say so and let the Director build it. A build that strays
outside your scope is opened as a draft PR and flagged, so stay inside it."""

# ---------------------------------------------------------------- backend

HERMES = shutil.which("hermes") or "/usr/local/bin/hermes"
_sem = asyncio.Semaphore(2)  # shared OAuth token; avoid hammering it


async def ask_hermes(persona: str, question: str, who: str, channel: str,
                     bot: str = "director", history: str = "") -> str:
    prompt = (
        f"{persona}\n\n"
        f"{repo_facts()}\n"
        f"{history}\n"
        f"You are running inside a scratch checkout of this repository at the path\n"
        f"below. You have file-read and search tools: OPEN the files rather than\n"
        f"guessing at their contents. Any write you make here is discarded and never\n"
        f"reaches the repo, so do not claim to have changed anything.\n"
        f"Discord #{channel} | asked by {who}\n"
        f"Question: {question}\n\n"
        f"Reply with the message text only."
    )
    async with _sem, builder.read_lock(bot):
        tree = await builder.ensure_read_tree(REPO, bot)
        cwd = tree or REPO
        try:
            proc = await asyncio.create_subprocess_exec(
                HERMES, "-z", prompt,
                "-t", "file",
                # Load-bearing: without these the CLI restores a previous
                # session's cwd and the "read-only" chat call ends up sitting in
                # the shared checkout instead of the disposable read tree.
                "--in", str(cwd), "--no-restore-cwd",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )
            out, err = await asyncio.wait_for(proc.communicate(),
                                              timeout=HERMES_TIMEOUT)
        except TimeoutError:
            log.warning("hermes timeout after %ss", HERMES_TIMEOUT)
            return (
                f"I timed out after {HERMES_TIMEOUT // 60} minutes — that's "
                "my failure, not a problem with your question. Nothing was written "
                "or changed; I have no memory of this attempt, so re-send and "
                "I'll start clean. If it was a long paste, sending just the "
                "specific ask usually gets through."
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
            hist = await recent_context(interaction.channel, self.user)
            ans = await ask_hermes(self.persona, question,
                                   interaction.user.display_name,
                                   getattr(interaction.channel, "name", "dm"),
                                   bot=self.name, history=hist)
            await interaction.followup.send(ans[:MAX_DISCORD])

        @self.tree.command(name="build",
                           description="Implement a change on a branch and open a PR",
                           guild=guild)
        @app_commands.describe(
            task="What to implement. Be specific: files, behaviour, tests.")
        async def _build(interaction: discord.Interaction, task: str):
            await interaction.response.defer(thinking=True)
            chan = interaction.channel

            async def progress(msg: str) -> None:
                try:
                    if isinstance(chan, discord.abc.Messageable):
                        await chan.send(f"🔨 **{self.name}** — {msg[:500]}")
                except discord.DiscordException:
                    self.log.warning("progress send failed", exc_info=True)

            self.log.info("BUILD by %s: %s", interaction.user.display_name, task[:120])
            # A /build task is usually the tail of a conversation ("do that, but
            # for ETH"). Without the transcript the builder would have to guess
            # what "that" was - and guessing is exactly what it must not do.
            hist = await recent_context(interaction.channel, self.user)
            res = await builder.build(
                repo=REPO, bot=self.name, persona=self.persona, task=task,
                who=interaction.user.display_name, hermes_bin=HERMES,
                progress=progress, history=hist,
            )
            head = "✅" if res.ok else "⚠️"
            await interaction.followup.send(f"{head} {res.summary}"[:MAX_DISCORD])

        @self.tree.command(name="status", description="Project status",
                           guild=guild)
        async def _status(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            hist = await recent_context(interaction.channel, self.user)
            ans = await ask_hermes(
                self.persona,
                "Give a short status of the QuantForge project: current phase, "
                "what exists, what the next exit gate is.",
                interaction.user.display_name,
                getattr(interaction.channel, "name", "dm"),
                bot=self.name, history=hist)
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
            # skip_id: the message being answered is passed as the question, so
            # including it in the transcript would show it to the model twice.
            hist = await recent_context(msg.channel, me, skip_id=msg.id)
            ans = await ask_hermes(self.persona, q, msg.author.display_name,
                                   getattr(msg.channel, "name", "dm"),
                                   bot=self.name, history=hist)
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
