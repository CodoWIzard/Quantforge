# Apps

## Ordering constraint — read this before creating files here

Blueprint Part X §42 and AGENTS.md: **do not start the web app before the research loop
is proven.** The hardest uncertainty is whether the research/validation workflow is
genuinely valuable, not whether a dashboard can be built.

`apps/web` is Experiment **010** — the last rung of the ladder. It wraps a core that
already works from the CLI.

`apps/api` (FastAPI, §13) may begin earlier, when the research loop needs job
orchestration and persistence (around Experiment 006–007). Its contract is already
frozen in `data-contracts/openapi.yaml`, so it can be built against without guessing.
