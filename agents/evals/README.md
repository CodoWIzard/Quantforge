# Evaluation Lab

Blueprint §17. Repeatable tests for whether the prototype is getting **more reliable or
worse** — the Week 4 board card.

Run it:

    .venv/bin/python agents/evals/run_lab.py --json agents/evals/runs   # score
    .venv/bin/python agents/evals/demo_month1.py                        # Month 1 demo

Exit 0 = every critical assertion held. Failures print the offending fixture ids and the
reason, never a percentage.

## Structure

    evals/
      rubric.json            8 scoring dimensions, machine-readable — the harness reads THIS
      scoring.md             prose mirror of rubric.json (a test asserts they agree)
      controls.json          isolation controls: one property each, everything else complete
      run_lab.py             deterministic scorer over the committed corpora + controls
      demo_month1.py         idea -> StrategySpec -> review -> tool-backed output
      RESULTS_LOG_FORMAT.md  the per-run record schema
      FAILURE_LOG.md         defects found BY RUNNING it, with reproductions
      runs/                  run records (gitignored; the format is committed, not the data)
      fixtures/              5 original §18 scenarios, agent-layer, not yet runnable

The bulk of the corpus lives in `experiments/002-strategy-compiler/`: 20 ideas
(`ideas/I001-I020.json`) and 18 impossible/unsafe requests (`unsafe/U001-U018.json`).
The lab drives those rather than duplicating them.

## Two layers, and the difference matters

- **deterministic** — `run_lab.py` drives the real compiler. No model, no network, no
  credentials, so it runs in CI. Scores schema adherence, clarification quality,
  no-invented-parameter and refusal-for-the-right-reason.
- **model** — tool usage, groundedness, criticism quality and self-review disclosure need
  a live model (`services/discord-bots/smoke_research.py`). **Unmeasured today.** The lab
  prints them as NOT MEASURED, because a dimension missing from a report reads as one
  that passed.

## The one thing to understand before trusting a number

Running the 13 REJECT-class unsafe fixtures gives **13/13 refused**, which looks like
proof the system rejects danger. It is not. Every one of those fixtures is raw prose,
therefore under-specified, therefore refused for a missing stop loss — and its actual
danger is never examined. All 13 raise the same error with the same message.

`controls.json` is the fix: each control is complete in every respect except the single
property under test, so a refusal cannot be explained away by vagueness. That is where
the safety evidence lives. See `FAILURE_LOG.md` F-001, and F-002 for the real defect this
technique uncovered (the 2% hard risk limit is documented but unenforced).

## Scoring dimensions (§17 step 4)

task completion · instruction adherence · tool selection and input accuracy ·
groundedness · domain-specific assertions

## Rules

- A fixture asserts **behaviour**, not exact wording. "Asked for a volume threshold"
  passes; a specific sentence does not.
- Adversarial fixtures (prompt injection, "just make it profitable") are as important as
  the happy path — they are where the product's credibility lives.
- Run the smoke subset on every change; the full suite at milestones (§19).
