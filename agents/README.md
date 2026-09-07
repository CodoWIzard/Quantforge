# Agents

Blueprint §14: during the internship you are **configuring and evaluating** agents, not
training models. An agent here = model + instructions + allowed tools + output schema +
evaluation criteria.

Each agent directory holds the same four things, so they can be diffed and versioned:

    <agent>/
      instructions.md    # behavioural contract - the system prompt, versioned
      tools.json         # tool allowlist. Least privilege (§34)
      output.schema.json # the structured shape it must return
      README.md          # role, model class, hard boundary

## Roles and hard boundaries (§15)

| Agent | Model class | Hard boundary |
|---|---|---|
| research-director | strong | Cannot calculate final metrics or place orders |
| strategy-specialist | small/medium | Cannot invent unresolved parameters silently |
| critic | strong | Must not optimise the strategy while judging that version |

The blueprint also names Data Auditor, Research Planner, Risk Reviewer and
Report/Explainer. They are deliberately **not** scaffolded yet — §42 says prove the loop
first. Add a directory when an experiment needs that role, not before.

## Improvement order (§17)

Fix the system before changing the model: schema, tool descriptions, instructions and
deterministic checks first. Benchmark models only after the contract is stable. No
fine-tuning until evaluation evidence justifies it (ADR-008).
