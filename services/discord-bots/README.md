# Discord bots

Two bots in one process, each with its own gateway connection so both appear
online and reply under their own identity.

| Bot | Purpose |
|---|---|
| `Research_Director` | Plans research, challenges evidence, refuses to fabricate metrics |
| `Admin-bot` | Project ops: repo structure, ADRs, CI, cost telemetry |

## How to talk to them
- `@Research_Director <question>` — works in any channel
- `/ask <question>` — slash command, either bot
- `/status` — project status
- Reply to one of their messages

## Service management
```bash
systemctl status quantforge-bots
systemctl restart quantforge-bots
journalctl -u quantforge-bots -f
```

Enabled at boot. Restarts on crash (max 5 attempts / 5 min).

**Restart takes ~40 seconds, not instant.** Discord throttles repeated gateway
identifies; the process logs "logging in using static token" and then pauses
before reaching ONLINE. This is expected — do not assume a hang and restart
again, which makes the throttling worse.

## Verification
```bash
.venv/bin/python -m pytest -q          # 17 contract tests
.venv/bin/ruff check .
npx pyright services/discord-bots/bots.py
```

## Credentials
`/root/.config/quantforge/discord.env` — mode 600, outside the repo.
Never commit tokens. CI fails the build if one is detected.

## Safety invariants (enforced by tests)
- Bots never produce authoritative numeric results (ADR-003)
- Bots never place or simulate orders (ADR-002)
- Bots never invent unspecified strategy parameters
- Bots ignore other bots (prevents infinite reply loops)
