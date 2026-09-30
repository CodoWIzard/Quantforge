# Experiment 001 — result

**Status:** RUN 2026-09-28, then RE-RUN clean the same day after fixing F-005.
Gate MET, and the result is now usable for what it was meant to unblock.
**Gate:** Reliable authentication, logging and cost visibility.

## Hypothesis

A single model call through the local `hermes` CLI would return schema-shaped JSON,
proving authentication, logging and cost visibility, and unblocking the four
model-layer evaluation dimensions that `run_lab.py` prints as NOT MEASURED.

## What was actually built

`experiments/001-model-call/run_001.py` (written 2026-09-09, never recorded as run
until today). Sends one structured prompt via `hermes -z`, then asserts: process
exit 0, non-empty stdout, stdout parses as JSON, required keys present,
`status == "ok"`. Records elapsed seconds. Exit 0 = gate met.

## Evidence

    $ .venv/bin/python experiments/001-model-call/run_001.py
    Authentication : OK (hermes responded)
    Structured JSON: OK (keys: ['experiment', 'message', 'status'])
    Model message  : Model call succeeded and the MNQ1! futures trading assistant
                     is online and ready.
    Compute seconds: 4.22s
    EXIT=0

Token counts, via `hermes -z ... --usage-file` (a flag the script does not yet use):

    {"estimated_cost_usd": 0.055254, "input_tokens": 3, "output_tokens": 39,
     "cache_write_tokens": 14576, "total_tokens": 14618, "api_calls": 1,
     "model": "claude-sonnet-4-6", "provider": "anthropic", "completed": true}

## Gate met?

- [x] Reliable authentication — call succeeded, exit 0, repeatable
- [x] Logging — stdout is the log; `--usage-file` writes a machine-readable record
- [x] Cost visibility — **upgraded from PARTIAL to full.** `run_001.py` says
      "hermes does not yet surface per-call token usage in stdout" and tells the
      reader to copy numbers off a provider dashboard by hand. `--usage-file PATH`
      does surface them, is written even when the run fails, and costs nothing.
      The script's own text is now the stale part, not the capability.

## What surprised us

**The model knew things the prompt never said.** The fixture prompt contains no
instrument, no account size and no project name. The reply came back naming
`MNQ1!`. A direct probe confirmed it:

    $ hermes -z "what is my primary futures instrument and trading project?
                 If you do not know, say exactly NO CONTEXT AVAILABLE."
    MNQ1! micro Nasdaq futures, paper trading a disciplined research bot with a
    $25,000 starting account.

That is Jaedyn's personal trading context arriving from the operator's Hermes
profile, not from QuantForge. `--ignore-user-config --ignore-rules` did **not**
suppress it — the same probe then leaked *more* (a gold MGC bot and a January 2027
live-deployment target). The 14,576 cache-write tokens against a 3-token prompt are
that injected context, measurable in the usage file.

The isolation boundary is the **profile**, not a flag:

| invocation | answer |
|---|---|
| `hermes -z` (sticky default = `futures`) | leaks MNQ1!, $25k, MGC, Jan 2027 |
| `hermes -p default -z` | leaks MNQ1! + QuantForge path |
| `hermes -p dev -z` | `NO CONTEXT AVAILABLE` |

`services/discord-bots/bots.py:898` resolves `HERMES = shutil.which("hermes")` and
passes no `-p`, so all six personas inherit whichever profile is sticky at the time.
See FAILURE_LOG F-005.

## Re-run after the fix (same day)

    $ .venv/bin/python experiments/001-model-call/run_001.py
    profile       : quantforge
    Authentication : OK (hermes responded)
    Structured JSON: OK (keys: ['experiment', 'message', 'status'])
    Model message  : Model call succeeded and Claude Sonnet 4-6 is responding
                     correctly as a test fixture for QuantForge Experiment 001.
    Compute seconds: 5.09s
    Tokens         : 3 in / 45 out / 2185 cache-write / 12797 total
    Cost           : $0.01204695 (1 call, claude-sonnet-4-6 via anthropic)
    Contamination probe (F-005): clean, backend replied 'UNKNOWN'
    Experiment 001 exit gate: MET.
    EXIT=0

The reply now names the model rather than the operator's instrument, and cache-write
tokens fell from **14,576 to 2,185** for the same 3-token prompt. The token count is
the objective evidence; the reply wording is a model choice that could vary between
runs, so it is not the thing to rely on.

The script now enforces what it previously only reported: it passes `-p`, reads token
counts and cost from `--usage-file`, and runs a contamination probe as a separate call
whose failure fails the experiment. Cost visibility is PASSED, not PARTIAL.

## Does the gate license the next step?

Now yes. Before the fix it did not: the gate wording ("authentication, logging, cost
visibility") never asked whether the call was *clean*, so a green gate would have
licensed scoring the model layer against a contaminated backend. Recorded rather than
silently reinterpreted, and the probe now makes the clean property part of the gate
instead of a caveat in prose.

## Decision

**Proceed.** F-005 is fixed under ADR-013 (dedicated `quantforge` profile, explicit
`-p` everywhere, required keyword in `builder.build()`). The model layer of
`run_lab.py` is no longer blocked by contamination.

Verified three independent ways: the script's own probe, the token-count drop, and
`services/discord-bots/probe_isolation.py` — a live end-to-end run through
`bots.ask_hermes`, the exact path the six personas use, returning UNKNOWN on 3/3
probes with none of the previously-leaked strings.

## Measured cost

| Item | Value |
|---|---|
| Model tokens (in/out) | 3 in / 39 out; 14,576 cache-write; 14,618 total |
| Estimated cost | $0.055254 (1 api call, claude-sonnet-4-6) |
| Compute seconds | 4.22s |
| Storage touched | none beyond stdout + the usage JSON |
