# critic

**Model class:** strong reasoning model
**Job:** Try to falsify the strategy. Challenge the methodology, the sample and the conclusions.

**Hard boundary (§15):** Must not optimise or repair the strategy while judging that version - that is a separate role and a separate version.

## Files

| File | Purpose |
|---|---|
| `instructions.md` | The versioned behavioural contract. Changing it is a reviewable diff. |
| `tools.json` | Tool allowlist — least privilege (§34). No generic shell/URL/secret tool. |
| `output.schema.json` | The structured shape this agent must return. |

## Evaluation

Scored against the fixtures in `agents/evals/fixtures/`. See §17: fix the schema, tools
and instructions before reaching for a bigger model.
