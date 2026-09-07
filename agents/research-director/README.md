# research-director

**Model class:** strong reasoning model
**Job:** Understand intent, create a research plan, delegate to specialists, decide whether the accumulated evidence is sufficient.

**Hard boundary (§15):** Cannot calculate final metrics. Cannot place orders. Cannot declare a verdict the validation battery did not produce.

## Files

| File | Purpose |
|---|---|
| `instructions.md` | The versioned behavioural contract. Changing it is a reviewable diff. |
| `tools.json` | Tool allowlist — least privilege (§34). No generic shell/URL/secret tool. |
| `output.schema.json` | The structured shape this agent must return. |

## Evaluation

Scored against the fixtures in `agents/evals/fixtures/`. See §17: fix the schema, tools
and instructions before reaching for a bigger model.
