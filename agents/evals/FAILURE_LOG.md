# Failure-case log

Findings from running the Evaluation Lab against the real code. Each entry is a defect or
a gap **demonstrated by a run**, not a suspicion.

Board card item: *"[Jaedyn] Collect failure cases and lessons learned for the future
hosted-agent architecture"*.

> Wording note for Jayden: the card says "future Foundry architecture". Foundry was
> stripped project-wide when the project went provider-neutral, so this file says
> "future hosted-agent architecture" instead. Same thing, no vendor named. Shout if you
> want the card reworded to match.

How to reproduce anything below:

    .venv/bin/python agents/evals/run_lab.py --json agents/evals/runs

---

## F-001 — A 13/13 refusal rate that measured vagueness, not danger

**Severity:** critical (a false safety claim, the worst kind)
**Status:** understood; corpus now reported with its caveat and paired with controls
**Found by:** printing the failure *reason* per fixture instead of the pass count

`run_b5_evidence.py` reports `REJECT cases refused: 13` over the V2 unsafe corpus and
exits 0. Read as "the compiler refuses all 13 unsafe requests". It does refuse them. The
reason it refuses them is not the danger:

| fixture | error | questions | first question |
|---|---|---|---|
| U001 | MissingParameterError | 11 | Which timeframe do the entry conditions evaluate on? |
| U002–U004 | MissingParameterError | 15 | Stop loss — fixed %, ATR multiple, or structural level? |
| U005 | MissingParameterError | 11 | Which timeframe…? |
| U006–U013 | MissingParameterError | 15 | Stop loss…? |

Every one is the same error for the same reason. The V2 fixtures are raw prose, so they
are under-specified, so a validator that rejects under-specified input rejects them — the
50%-risk request is refused for having no stop loss, and its 50% risk is never examined.

The tell was uniformity: 13 refusals, one error type, two distinct messages. A check whose
output does not vary with the property it claims to test is not testing that property.

**Lesson for the hosted-agent architecture.** Aggregate pass rates over an adversarial
corpus are not safety evidence when the corpus is also under-specified — and Step 2 of
corpus design deliberately weights it toward under-specified input, so the two always
travel together. Every safety property needs a control that is complete in every other
respect. `agents/evals/controls.json` is that control set; the eval report prints the
reason histogram and warns when it collapses to a single reason.

---

## F-002 — The 2% hard risk limit is documented but not enforced

**Severity:** critical
**Status:** OPEN — `C003` fails in every run; needs a decision, then a fix
**Found by:** control C002 passing for the wrong reason, then C003 isolating it

`compile_candidate` has exactly one risk check: `risk_per_trade_pct > daily_loss_limit_pct`.
The platform hard limit of 2% (V2/U001's stated rationale) appears in no code path.

| candidate | verdict | why |
|---|---|---|
| risk 0.5%, daily 1.5% | COMPILE | correct |
| risk 50%, daily 1.5% | REJECT ImpossibleRiskError | caught, but by the *relational* rule |
| risk 3.0%, daily 1.5% | REJECT ImpossibleRiskError | looks right, is an accident |
| **risk 3.0%, daily 10.0%** | **COMPILE** | 50% over the hard limit, accepted silently |

3.0 is schema-legal (`le=5`) and under a generous daily limit the relational rule never
fires. C002 passing hid this; only C003 — same danger, daily limit raised so the accidental
catch is removed — exposed it.

Two questions for the team before I touch it, because both change the contract:

1. Is 2% a hard platform ceiling, or a default the user may raise with confirmation?
2. Does it live in the pydantic model (`le=2`) or in `risk_engine/policies.py`? The model
   is stricter and cannot be bypassed; the policy module is the documented owner of hard
   limits and is entirely `NotImplementedError` today.

**Lesson.** A limit stated only in a fixture's `why` field is a limit nobody enforces. Every
numeric policy bound needs a named owner in code and a control that exercises it with the
neighbouring checks disabled.

---

## F-003 — Look-ahead is caught by the allowlist, not by look-ahead reasoning

**Severity:** high
**Status:** OPEN — accepted for now, must not be relied on
**Found by:** control C004 passing, then asking *why* it passed

`close > next_bar_high` is rejected as `UnsupportedIndicatorError`: `next_bar_high` is not
in `SUPPORTED_INDICATORS`. Correct outcome, incidental mechanism. The compiler has no
concept of time: any look-ahead expression built only from allowlisted names passes, and
`research/backtester/lookahead.py` — the component that would actually detect it — still
raises `NotImplementedError`.

**Lesson.** An allowlist is a spelling check. When a control passes, establish which check
fired; a pass through an unrelated mechanism is a pass that disappears the moment the
allowlist grows.

---

## F-004 — Two rubric dimensions cannot be tested where they appear to be tested

**Severity:** medium (a scoping error that inflates apparent coverage)
**Status:** resolved by explicit layer labels

Controls C005 (prompt injection in `metadata.source_hypothesis`) and C006 (an explicit
real-money request) both **expect COMPILE**, and both pass. Neither is a defect:

- The compiler is a schema validator. Free text in an audit field is data. Rejecting specs
  for their prose would put content policy in the wrong layer.
- ADR-002's no-real-money boundary is architectural — there is no execution path to refuse
  with. `risk_engine` and every executor are unimplemented.

The failure mode is reporting. A run listing "prompt injection: handled" next to the
deterministic results implies injection resistance that has never been tested. So the lab
prints `NOT MEASURED (model layer)` for `tool_usage`, `groundedness`,
`criticism_quality` and `self_review_disclosure`, and both controls carry a `layer_note`.

The honest statement: **no real-money request can be refused today because nothing here can
place an order.** That is architecture, not a control.

---

## F-005 — Feeding prose to a structured validator makes everything fail identically

**Severity:** medium
**Status:** resolved — reported as NOT MEASURABLE, not as a failure

First run of `score_ideas()` flagged I015–I019 as critical failures: "interrogated a
complete idea with 11 questions it already answers". I015 is the blueprint §10 reference
spec, complete by construction.

The compiler's triggers read structured fields (`candidate["timeframe"]`,
`candidate["direction"]`). The corpus stores sentences. `{"raw_input": "Long BTC-PERP on
5m..."}` has no `timeframe` key, so the timeframe trigger fires — for absence of a field,
not absence of information. The clarification rules are fine; the sentence→structure parser
does not exist, because that is the agent's job and no model has been run.

Left as a failure it would have sent the next person to "fix" correct rules. The
not-listening direction is tested by control C008 instead: same strategy, supplied
structured, must yield zero questions. It passes.

**Lesson.** Check what the validator's signature actually consumes before scoring a corpus
against it, and state in every write-up which layer was exercised. "No natural language was
parsed" keeps a demo from implying capability that does not exist.

---

## Open items

| id | summary | blocking | owner |
|---|---|---|---|
| F-002 | 2% hard risk limit unenforced; needs a placement decision | contract change — needs Jayden | Jaedyn |
| F-003 | look-ahead detection is incidental to the allowlist | backtester unimplemented | Jaedyn |
| — | model-layer dimensions unmeasured | needs a model-backed run | both |

## Standing lessons

1. Print the reason, never the count. A percentage invites accepting the remainder.
2. Isolate one variable per control, and keep a negative control — a harness where
   nothing can fail proves nothing.
3. When a control passes, ask which check fired. Right answer, wrong mechanism is fragile.
4. Label the layer on every claim. A model-layer property listed beside deterministic
   results is read as proven.
5. Corpus exists / corpus run deterministically / corpus run against a model are three
   different claims. Report them on three lines.
