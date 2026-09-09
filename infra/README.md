# Infrastructure

Blueprint Part VII. The governing rule: **use Azure where it teaches or enables
something; keep everything else local until it earns its bill.**

## Layout

    infra/
      terraform/     # Azure resources as code
      docker/        # service Dockerfiles + compose for local dev
      cron/          # host-side scheduled jobs (existing bot board refresh)
      systemd/       # host-side unit files (existing Discord bots)

## Service introduction order (§30)

| Service | When to introduce |
|---|---|
| Hosted model endpoint | Experiment 001 |
| Blob / Data Lake | as soon as collection starts |
| Key Vault | before real secrets enter the cloud |
| Container Apps + Jobs | after local containerised backtest works |
| PostgreSQL Flexible Server | after the research loop needs persistence |
| App Insights / Monitor | when first services deploy |
| Container Registry | first Container Apps deployment |
| Entra External ID | SaaS integration phase |
| **Managed Redis** | **never during the internship (ADR-006)** |

## Budget (§33)

Five-month planning envelope **~€205–€855**, targeting €300–€500 with disciplined
experiments. Create Azure budgets and alerts **on day one** — the blueprint calls cost
telemetry a product feature, not an afterthought.

| Category | Range |
|---|---|
| Model inference / agents / evals | €100–€500 |
| Container Apps + Jobs | €75–€150 |
| PostgreSQL | €0–€80 |
| Blob / Data Lake | €10–€50 |
| Key Vault, monitoring, registry | €10–€50 |
| Managed Redis | €0 (excluded) |
| Premium market data | €0 (not required) |
