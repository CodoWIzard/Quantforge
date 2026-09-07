# Evaluation fixtures

Blueprint §17 step 2: build **50–100 trading scenarios** containing ambiguous ideas,
misleading backtests, missing data, suspicious metrics and adversarial prompts — each
with the expected behaviour recorded.

The launch checklist requires the **first 20 fixtures before serious build**.

## Structure

    evals/
      fixtures/           # one JSON per scenario
      run_evals.py        # harness: run fixtures against an agent, score, report
      scoring.md          # what "correct" means per §17 step 4

## Scoring dimensions (§17 step 4)

task completion · instruction adherence · tool selection and input accuracy ·
groundedness · domain-specific assertions

## Rules

- A fixture asserts **behaviour**, not exact wording. "Asked for a volume threshold"
  passes; a specific sentence does not.
- Adversarial fixtures (prompt injection, "just make it profitable") are as important as
  the happy path — they are where the product's credibility lives.
- Run the smoke subset on every change; the full suite at milestones (§19).
