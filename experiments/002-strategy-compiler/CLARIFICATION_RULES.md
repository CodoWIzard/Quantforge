# B4 — Clarification rules

**Owner:** Jaedyn · **Task:** Add clarification rules for missing breakout, volume, exit,
timeframe and risk definitions · **Experiment:** 002 — strategy compiler

The governing rule, from AGENTS.md and blueprint §18:

> Never invent an unspecified strategy parameter. Missing values are **errors**, not defaults.

Asking is a success path, not a failure path. Exit gate for Experiment 002 is
*"10–20 test prompts produce no silent invented parameters"* — these rules are how that
gate is met.

## How the compiler uses this

1. Parse the candidate against `strategy-spec.schema.json`
2. For every rule below whose **trigger** matches, emit its questions
3. If any question is outstanding → return `{"kind": "questions"}`, do **not** compile
4. Only when zero questions remain → produce a StrategySpec

Questions are returned **all at once**, never one at a time — a user should answer a
single form, not survive an interrogation.

---

## Breakout

**Trigger:** Input mentions break/breakout/breaks above/below, or names a level without defining it.

**Why it matters:** 'Breakout' silently bundles four independent decisions. Guessing any one of them changes the trade count by an order of magnitude.

**Ask:**
- Which level exactly - previous N-period high/low, session high, a round number, or a drawn level?
- Over what lookback window is that level computed?
- Does an intrabar touch count, or only a confirmed close beyond the level?
- Any buffer past the level before it counts (e.g. 0.05%)?

**Never:** Default to 'previous 4h high' because the blueprint example used it. That example is one instance, not a default.

**Compiles to:** `entry.conditions[].expression + lookback_bars`

---

## Volume

**Trigger:** Input mentions volume, 'high volume', 'unusual volume', or volume confirmation.

**Why it matters:** Volume needs a baseline AND a multiple. Either alone is meaningless. §18 names inventing '1.5x' as the canonical failure.

**Ask:**
- Volume relative to what baseline - a simple MA, median, or same-hour-of-day average?
- What period for that baseline?
- What multiple counts as high (e.g. 1.5x)?
- Measured on the signal timeframe or a higher one?

**Never:** Assume 1.5x, assume sma(volume,20), or treat raw volume as comparable across timeframes.

**Compiles to:** `entry.conditions[].expression`

---

## Exit

**Trigger:** Input has entry logic but no stop, target, or time limit. Also 'let winners run', 'exit when it reverses'.

**Why it matters:** An unbounded strategy has no risk profile and cannot be sized, backtested honestly, or approved. The schema requires at least one bounded exit.

**Ask:**
- Stop loss - fixed %, ATR multiple, or structural level?
- Take profit, or exit on an opposite signal?
- Maximum holding time before exiting regardless?
- If both stop and target could be hit in the same bar, which takes priority?

**Never:** Add a default stop. A strategy without an exit is incomplete, not a strategy with an implied one.

**Compiles to:** `exit.stop_loss_pct / take_profit_pct / max_holding_minutes`

---

## Timeframe

**Trigger:** No timeframe stated, or signal and execution timeframes differ, or an out-of-scope timeframe.

**Why it matters:** The same rule on 1m and 15m is two different strategies. Scope is 1m/5m/15m only (§6); a 4h signal needs an explicit multi-timeframe decision.

**Ask:**
- Which timeframe do the entry conditions evaluate on - 1m, 5m or 15m?
- If a condition references a higher timeframe, does execution stay on the lower one?
- Must the higher-timeframe bar be closed before the signal is valid?

**Never:** Infer a timeframe from the indicator period, or silently execute on the signal timeframe.

**Compiles to:** `timeframe + rule.lookback_bars`

---

## Risk

**Trigger:** No risk block, or qualitative sizing ('small size', 'go big', 'tight stops').

**Why it matters:** Risk is mandatory in the schema and enforced by the risk engine. Qualitative sizing cannot be enforced or backtested.

**Ask:**
- What percentage of account equity is risked per trade?
- What daily loss limit halts trading for the day?
- How many positions may be open at once?
- Any maximum notional exposure cap?

**Never:** Copy risk values from another strategy or use the schema maximum as a default.

**Compiles to:** `risk.risk_per_trade_pct / daily_loss_limit_pct / max_open_positions`

---

## Indicator Params

**Trigger:** An indicator is named without its period, or a threshold without the indicator.

**Why it matters:** RSI(9) and RSI(21) generate different trades from the same words. An unstated period is a hidden free parameter - exactly what sensitivity testing later punishes.

**Ask:**
- Which period for that indicator?
- Which price input - close, hlc3, typical price?
- What exact threshold, and is the comparison strict or inclusive?

**Never:** Use the 'standard' period. Conventional defaults are still invented parameters.

**Compiles to:** `entry.conditions[].expression`

---

## Direction

**Trigger:** Direction not stated, or a symmetric rule is described without confirming both sides trade.

**Why it matters:** Long-only and long/short have different exposure and different regime dependence.

**Ask:**
- Long only, short only, or both?
- If both, are the conditions mirrored exactly or defined separately?

**Never:** Assume long-only because the example was bullish.

**Compiles to:** `direction`

---

## Market

**Trigger:** No market named, or a market outside BTC-PERP / ETH-PERP.

**Why it matters:** ADR-001 restricts internship scope to BTC and ETH perpetuals on one exchange.

**Ask:**
- BTC-PERP or ETH-PERP?
- If both, one spec per market or shared parameters?

**Never:** Accept an out-of-scope symbol. That is a scope rejection with an explanation, not a clarification.

**Compiles to:** `market`

---

## Escalation

If the user declines to answer ("just pick something sensible"):

1. Explain that an invented parameter makes the backtest meaningless — the result would
   measure our guess, not their idea.
2. Offer **explicit named options** with their trade-offs, and let the user choose.
3. If they still decline, stop. Do not compile. A refusal to specify is a valid end state.

Offering options is not the same as defaulting: the user still makes the choice, and the
choice is recorded in `metadata.clarifications` for audit.

## Anti-patterns observed while drafting

| Anti-pattern | Why it fails |
|---|---|
| "I'll use the standard RSI period" | A convention is still an invented parameter |
| "The blueprint example used 1.5x volume" | One example is not a default |
| "Tight stop → I'll assume 0.5%" | Qualitative words have no numeric mapping |
| Asking questions one at a time | Turns a 30-second form into a 10-message ordeal |
| Compiling with a `null` and fixing later | The null reaches the backtester and produces a number nobody can defend |
