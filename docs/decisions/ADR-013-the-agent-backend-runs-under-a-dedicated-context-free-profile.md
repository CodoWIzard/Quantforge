# ADR-013: The agent backend runs under a dedicated, context-free profile

Status: Accepted
Date: 2026-09-28
Deciders: Jaedyn

## Context

Every AI call in this project shells out to the local `hermes` CLI. Running
Experiment 001 showed that a bare `hermes -z` inherits whichever profile is
*sticky on the host* and silently prepends that profile's personal context to the
prompt.

The fixture prompt for Experiment 001 names no instrument, no account size and no
project. The reply named `MNQ1!`. Probing directly returned the operator's
personal trading context: MNQ1!, a $25,000 paper account, and — with
`--ignore-user-config --ignore-rules` set — a gold MGC bot and a January 2027
live-deployment date. The flags that read like the fix are not the fix; the probe
leaked *more* with them set. Roughly 12–15k cache-write tokens against a 3-token
prompt is that context arriving, and it is measurable in `--usage-file`.

Three properties make this worse than an ordinary leak:

1. **The facts are true**, so no downstream validator, critic or reviewer flags them.
2. **They never appear in the transcript**, so "the model invented this ticker" and
   "the host profile supplied it" are indistinguishable after the fact.
3. **The profile can change with no code change and no log line**, so a run is not
   reproducible — which violates the reproducibility rule in AGENTS.md.

It also blocks the Evaluation Lab. `run_lab.py` reports four dimensions as NOT
MEASURED pending a model endpoint, one of which is **groundedness**. Scoring
groundedness against a contaminated backend measures the operator's profile, and
it would score *well*, because the supplied facts are correct. A metric that
rewards the behaviour it exists to detect is worse than no metric.

## Decision

A dedicated `quantforge` Hermes profile is part of this system's deployment, and
**every programmatic invocation passes `-p` explicitly.**

- The profile is created with no personal context: empty `memories/USER.md`, the
  default SOUL.md, no trading history.
- `bots.py` exposes `HERMES_PROFILE`, overridable via
  `QUANTFORGE_HERMES_PROFILE` for local experimentation, defaulting to
  `quantforge`. Both the chat path and the build path pass it.
- `builder.build()` takes `hermes_profile` as a **required keyword argument**. A
  new call site cannot forget it; it fails at the call, not at runtime in a way
  that looks like a model quirk.
- `experiments/001-model-call/run_001.py` passes `-p` and ends with a
  contamination probe: it asks for facts the prompt never gave and fails unless
  the backend answers `UNKNOWN`.
- `tests/test_backend_isolation.py` asserts the convention from source text — no
  model call, so it runs in CI.

`default` and `futures` are explicitly forbidden as values. Both were verified to
leak, and `-p default` is the tempting wrong answer.

## Alternatives considered

**`--ignore-user-config` / `--ignore-rules`.** Rejected on evidence: does not
suppress profile context, and leaked additional facts in testing. Worse than
useless — it reads like a fix, so a future reader would believe the leak was
closed.

**Reuse the `dev` profile.** It probes clean today, but it is a human's working
profile: it accumulates context as it is used, and nothing stops that. Borrowing
someone's profile makes the isolation property incidental rather than owned.

**Strip context in the prompt.** Cannot work. The injection happens above the
prompt layer; the prompt is what is being contaminated.

**Do nothing and note it in the eval report.** Rejected. The four model-layer
dimensions stay permanently unmeasurable, and the existing venue blind spot (a
run wrote "Binance, BTCUSDT perp" with no Binance module in the repo, and the
critic then certified nothing was invented) stays undiagnosable.

## Consequences

**Good.** Model-layer scoring becomes meaningful. Runs become reproducible —
the profile is named in the argv, so it is in the process list and the logs. The
bots lose access to context they were never entitled to. The probe means a future
regression fails a run instead of quietly degrading a metric.

**Cost.** One more deployment prerequisite: the profile must exist on any host
running the bots, and it needs its own API credentials. A missing profile is a
hard failure at call time rather than a silent fallback — deliberate, since a
silent fallback to the host's profile is the exact bug being fixed.

**Not covered.** This addresses context arriving from the *host profile*. It does
not address a model's parametric knowledge of, say, real tickers — that remains
the never-invent-a-parameter rule's job, and `agents/evals/controls.json` is where
it is tested. The two failure modes look identical in a transcript, which is
precisely why the environmental one had to be eliminated first.

## References

- `agents/evals/FAILURE_LOG.md` F-005 — the finding and its evidence
- `experiments/001-model-call/RESULT.md` — the run that exposed it
- `tests/test_backend_isolation.py` — the enforcing tests
- ADR-012 — venue decision, whose "Binance, BTCUSDT" symptom this explains
