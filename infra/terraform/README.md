# Terraform

Azure resources as code. Nothing here is applied yet — no Azure resources are
provisioned (see `CURRENT_STATE.md`).

## Intended module order

Introduce a module only when the corresponding experiment needs it (§30):

    modules/
      models/          # Experiment 001 - model deployment + agent
      storage/         # Blob/Data Lake, containers, lifecycle rules
      keyvault/        # secrets + managed identity access policies
      container-apps/  # environment, API, collector, jobs
      postgres/        # Flexible Server, small burstable, no HA
      monitoring/      # App Insights, budgets and cost alerts

## Rules

- **No Managed Redis module.** ADR-006. If someone adds one, that is an ADR change.
- Budgets and alerts land in the *first* apply, not the last.
- `*.tfvars` is gitignored; commit `*.tfvars.example` with placeholder values.
- Secrets come from Key Vault via managed identity — never a Terraform variable holding
  a real credential.
- State backend: remote (Azure Storage), configured before the first shared apply.
