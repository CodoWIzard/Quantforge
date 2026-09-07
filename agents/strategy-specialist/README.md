# strategy-specialist

**Model class:** small/medium, escalate on ambiguity
**Job:** Convert a vague trading idea into an explicit StrategySpec candidate, asking for anything undefined.

**Hard boundary (§15):** Cannot invent an unresolved parameter. Ever. A missing threshold is a question, not a default.

## Files

| File | Purpose |
|---|---|
| `instructions.md` | The versioned behavioural contract. Changing it is a reviewable diff. |
| `tools.json` | Tool allowlist — least privilege (§34). No generic shell/URL/secret tool. |
| `output.schema.json` | The structured shape this agent must return. |

## Evaluation

Scored against the fixtures in `agents/evals/fixtures/`. See §17: fix the schema, tools
and instructions before reaching for a bigger model.
