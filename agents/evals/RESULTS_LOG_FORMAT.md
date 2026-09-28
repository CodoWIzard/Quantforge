# Results log format

One JSON object per evaluation run, appended to `agents/evals/runs/runs.jsonl`
(JSON Lines: append-only, greppable, diffable, no parser needed).

    .venv/bin/python agents/evals/run_lab.py --json agents/evals/runs

Board card item: *"[Jayden] Add a simple results log format for each evaluation run"* —
drafted here so it is not blocking; Jayden owns the final call on the fields.

## Why these fields

The log exists to answer one question later: **did this change make the system better or
worse?** A score with no provenance cannot answer it — two runs are only comparable if the
commit, the rubric version and the control-set version are all recorded. A bare
`{"score": 0.87}` is unfalsifiable six weeks from now.

## Schema — `quantforge.eval-run/1`

| field | type | why it is here |
|---|---|---|
| `schema` | string | version tag; bump when fields change meaning |
| `run_id` | string | UTC compact timestamp, sorts chronologically |
| `timestamp_utc` | string | ISO-8601 |
| `layer` | `deterministic` \| `model` | **which half ran.** Without this a deterministic run reads as full coverage |
| `target` | string | what was scored, e.g. `packages/strategy_schema` |
| `provenance.commit` | string | short SHA — the only way to correlate a delta with a change |
| `provenance.branch` | string | |
| `provenance.dirty` | bool | uncommitted changes: the run is not reproducible, say so |
| `provenance.rubric_version` | string | a score under a changed rubric is not the same score |
| `provenance.control_set_version` | string | same, for the isolation controls |
| `provenance.python` | string | |
| `counts.*` | int | corpus sizes actually exercised, not the corpus sizes on disk |
| `dimensions_measured` | list | |
| `dimensions_not_measured` | list | **required, never omitted.** A dimension missing from a report reads as a dimension that passed |
| `results.controls_passed` / `controls_total` | int | |
| `results.has_discriminating_power` | bool | false = every control gave the same verdict, so the harness cannot fail and the run is void |
| `results.unsafe_reason_histogram` | object | error type -> count. The reason distribution, not a pass rate |
| `results.single_reason_for_every_refusal` | bool | true = refusals are explained by one shared cause; the corpus is not discriminating |
| `critical_failures` | list | `{id, dimension, detail}` — merge-blocking |
| `known_gaps` | list | same shape; demonstrated defects already logged in FAILURE_LOG.md, not blocking |
| `not_measurable` | list | scored cases where the *test setup* cannot measure the property (see F-005) |
| `verdict` | `PASS` \| `FAIL` | PASS means zero critical failures, nothing more |
| `elapsed_s` | float | |
| `honest_scope` | string | prose statement of what the run did NOT exercise |

## Rules

- **Append, never overwrite.** The history is the artifact; a single latest-result file
  cannot show a regression.
- **No aggregate percentage.** Per-fixture `detail` strings only. `17/20` invites someone
  to accept the 3.
- **`dimensions_not_measured` and `known_gaps` are never dropped to make a run look
  clean.** A PASS with four unmeasured dimensions is an honest PASS; a PASS that hides
  them is a false claim.
- **`verdict: PASS` is a narrow claim** — zero critical failures in the layer named by
  `layer`. It is not "the system works".
- `has_discriminating_power: false` **voids the run** regardless of verdict.

## Comparing two runs

Compare same-`layer`, same-`rubric_version` records:

    jq -s 'map({run_id, commit: .provenance.commit, verdict,
                ctl: "\(.results.controls_passed)/\(.results.controls_total)",
                crit: (.critical_failures | length)})' agents/evals/runs/runs.jsonl

A new id in `critical_failures` is a regression. A `known_gaps` entry disappearing is a
fix — confirm it was fixed rather than deleted from `controls.json`.

## Model-layer records (not yet emitted)

The model-backed pass will write `layer: "model"` records to the same file, adding
`model`, `prompt_version`, `tool_calls`, `retries`, `latency_s` and `cost_usd` per §17
step 3. Unwritten until a model runs — no placeholder records.
