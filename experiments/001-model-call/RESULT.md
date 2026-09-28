# Experiment 001 — result

**Status:** RUN 2026-09-28. Gate MET for the stated wording; a finding blocks
downstream use of the result (see F-005).
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

## Does the gate license the next step?

Yes as written, no in effect. The gate wording ("authentication, logging, cost
visibility") never asked whether the call was *clean*, so a pass here does not
license using this harness to score the model layer. Logged rather than silently
reinterpreted.

## Decision

**Proceed to 002/004 for the compiler and critic, but do NOT wire the model layer of
`run_lab.py` to `hermes -z` until F-005 is fixed.** Scoring groundedness against a
backend that supplies unearned facts measures the operator's profile, not the agent
— and it would score *well* while doing it, which is the failure mode that hides.

Two follow-ups, both small:
1. `run_001.py` should pass `--usage-file` and assert `completed == true`, then
   delete its manual-dashboard paragraph and report cost visibility as full.
2. Every programmatic `hermes` invocation needs an explicit `-p <clean-profile>`.

No ADR yet: the fix is an invocation convention, not an architecture change. If a
dedicated `quantforge` profile is created for the bots, that IS an ADR.

## Measured cost

| Item | Value |
|---|---|
| Model tokens (in/out) | 3 in / 39 out; 14,576 cache-write; 14,618 total |
| Estimated cost | $0.055254 (1 api call, claude-sonnet-4-6) |
| Compute seconds | 4.22s |
| Storage touched | none beyond stdout + the usage JSON |
