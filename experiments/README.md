# Experiments

Blueprint §42–43. These are **disposable learning artifacts with precise success
criteria** — not production code. The point is to answer the first technical question
before committing to architecture:

> Can QuantForge take a vague trading idea, convert it into a strict strategy, run a real
> deterministic backtest, criticise the evidence and produce a useful verdict?

## The ladder

| # | Experiment | Exit gate | Target |
|---|---|---|---|
| 001 | `001-foundry-call/` | Reliable authentication, logging and cost visibility. | Weeks 1-2 |
| 002 | `002-strategy-compiler/` | 10-20 test prompts produce no silent invented parameters. | Weeks 1-2 |
| 003 | `003-local-backtest/` | Known strategy results are reproducible. | Weeks 3-4 |
| 004 | `004-critic-loop/` | Critic catches intentionally planted weak strategies. | Weeks 9-10 |
| 005 | `005-containerise/` | Same result local and in container. | Weeks 7-8 |
| 006 | `006-azure-job/` | One API call -> Azure job -> stored result. | Weeks 7-8 |
| 007 | `007-persistence/` | Experiment can be reopened and reproduced. | Weeks 13-14 |
| 008 | `008-live-collector/` | Reconnect/gap/duplicate tests pass. | Weeks 3-4 |
| 009 | `009-paper-execution/` | End-to-end demo trade + reconciliation + kill switch. | Weeks 15-16 |
| 010 | `010-saas-shell/` | A new user can complete the whole workflow without CLI. | Weeks 17-18 |

## Rules

- An experiment is **done when its exit gate is demonstrated**, not when the code looks
  finished. Record the evidence in the experiment's own `RESULT.md`.
- Experiments may be messy. They may **not** be promoted into `packages/` or `research/`
  by copy-paste — a promotion is a reviewed PR with tests.
- Recommended immediate next action (blueprint's closing line): implement **001 and 002**.
- Do not provision Managed Redis, do not build billing, do not start a large web
  interface until the loop through 004 is convincing.
