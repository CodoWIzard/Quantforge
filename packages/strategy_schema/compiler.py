"""Natural-language candidate -> validated StrategySpec.

Blueprint §21 step 1 and Experiment 002. The exit gate is explicit:
*"10-20 test prompts produce no silent invented parameters."*

Flow::

    candidate (dict from the Strategy Specialist agent)
      -> validate against strategy-spec.schema.json
      -> check every indicator is in SUPPORTED_INDICATORS
      -> check risk values are internally consistent
      -> either a StrategySpec, or a list of clarification questions

Returning questions is a SUCCESS path, not an error path. The system is designed to ask
rather than to guess (§9 step 1).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from packages.strategy_schema.errors import (
    ImpossibleRiskError,
    MissingParameterError,
    UnsupportedIndicatorError,
)
from packages.strategy_schema.models import (
    SUPPORTED_INDICATORS,
    StrategySpec,
)

# ---------------------------------------------------------------------------
# Clarification rules loaded from the committed research artefact.
# This is the single source of truth — do not duplicate the text here.
# ---------------------------------------------------------------------------

_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "experiments/002-strategy-compiler/clarification_rules.json"
)

with _RULES_PATH.open() as _f:
    _CLARIFICATION_RULES: dict = json.load(_f)["rules"]


def _text_of(candidate: dict) -> str:
    """Flatten the candidate to a single lowercase string for keyword matching."""
    return json.dumps(candidate).lower()


def _triggers_breakout(candidate: dict) -> bool:
    """Trigger only when the word 'breakout/breaks above/below' appears in candidate
    fields that carry user intent (strategy_id, metadata.source_hypothesis) or in
    a condition expression that does NOT already reference a resolved level indicator.

    Rationale: an expression like 'close > previous_4h_high' is already resolved —
    the level is explicit. The trigger is for vague inputs like 'buy the breakout'.
    """
    # Check source_hypothesis for vague breakout language — NOT strategy_id,
    # which is a slug and may legitimately contain 'breakout' when the level is resolved.
    hypothesis = (candidate.get("metadata") or {}).get("source_hypothesis", "")
    vague_text = hypothesis.lower()
    if re.search(r"\bbreak(out|s?\s+(above|below))?\b", vague_text):
        return True

    # Check condition expressions — trigger only if they say "breakout" without
    # already naming the level (i.e. no supported level indicator present)
    entry = candidate.get("entry", {})
    conditions = entry.get("conditions", []) if isinstance(entry, dict) else []
    for cond in conditions:
        expr = (cond.get("expression", "") if isinstance(cond, dict) else "").lower()
        if re.search(r"\bbreak(out|s?\s+(above|below))?\b", expr):
            # It's vague if no supported level indicator already resolves it
            resolved = any(ind in expr for ind in SUPPORTED_INDICATORS)
            if not resolved:
                return True

    return False


def _triggers_volume(candidate: dict) -> bool:
    text = _text_of(candidate)
    return bool(re.search(r"\bvolume\b", text))


def _triggers_exit(candidate: dict) -> bool:
    """No stop, no target, no time limit, OR qualitative-only exit language."""
    has_exit = bool(candidate.get("exit"))
    if has_exit:
        ex = candidate["exit"]
        # qualitative phrases like "let winners run", "exit when it reverses"
        qualitative = re.search(r"let winner|exit when|reverses?", _text_of(ex))
        if qualitative:
            return True
        # must have at least one bounded exit
        return not (ex.get("stop_loss_pct") or ex.get("max_holding_minutes"))
    # no exit block at all
    text = _text_of(candidate)
    return not bool(re.search(r"\bstop\b|\btarget\b|\bmax.hold\b", text))


def _triggers_timeframe(candidate: dict) -> bool:
    tf = candidate.get("timeframe")
    if not tf:
        return True
    return tf not in ("1m", "5m", "15m")


def _triggers_risk(candidate: dict) -> bool:
    if not candidate.get("risk"):
        return True
    risk = candidate["risk"]
    text = _text_of(risk)
    return bool(re.search(r"\bsmall\b|\bbig\b|\btight\b|\bgo big\b", text))


def _triggers_indicator_params(candidate: dict) -> bool:
    """An indicator name appears without a period, or a threshold without its indicator."""
    text = _text_of(candidate)
    # Named indicators without an explicit number following them
    # matches e.g. "rsi" not followed by a period/paren -> period is unstated
    return any(
        re.search(rf"\b{ind}\b(?!\s*[\(\d])", text)
        for ind in ("rsi", "ema", "sma", "atr")
    )


def _triggers_direction(candidate: dict) -> bool:
    return not candidate.get("direction")


def _triggers_market(candidate: dict) -> bool:
    market = candidate.get("market")
    if not market:
        return True
    return market not in ("BTC-PERP", "ETH-PERP")


_TRIGGER_MAP = {
    "breakout": _triggers_breakout,
    "volume": _triggers_volume,
    "exit": _triggers_exit,
    "timeframe": _triggers_timeframe,
    "risk": _triggers_risk,
    "indicator_params": _triggers_indicator_params,
    "direction": _triggers_direction,
    "market": _triggers_market,
}


def clarification_questions(candidate: dict) -> list[str]:
    """Every question that must be answered before this candidate can compile.

    Returned all at once so the UI can ask them in a single guided pass instead of
    interrogating the user field by field.  Returns an empty list only when zero
    triggers fire.  Never returns a partial set (B4 rule is explicit on this).
    """
    questions: list[str] = []
    for rule_name, trigger_fn in _TRIGGER_MAP.items():
        if trigger_fn(candidate):
            rule = _CLARIFICATION_RULES.get(rule_name, {})
            questions.extend(rule.get("ask", []))
    return questions


# ---------------------------------------------------------------------------
# Indicator allowlist scanner
# ---------------------------------------------------------------------------

def _extract_indicator_names(expression: str) -> set[str]:
    """Return every word-token from an expression that looks like an indicator name."""
    # strip numbers, operators, punctuation — keep alphabetic tokens
    tokens = re.findall(r"[a-z_][a-z_0-9]*", expression.lower())
    # exclude comparison keywords and numeric words
    excluded = {"and", "or", "not", "if", "else", "true", "false"}
    return {t for t in tokens if t not in excluded}


def _check_indicators(entry: dict) -> None:
    """Raise UnsupportedIndicatorError for any indicator outside the allowlist."""
    conditions = entry.get("conditions", [])
    for cond in conditions:
        expr = cond.get("expression", "") if isinstance(cond, dict) else cond.expression
        for name in _extract_indicator_names(expr):
            if name not in SUPPORTED_INDICATORS:
                raise UnsupportedIndicatorError(name)


# ---------------------------------------------------------------------------
# Risk consistency check
# ---------------------------------------------------------------------------

def _check_risk_consistency(risk: dict) -> None:
    """Raise ImpossibleRiskError for contradictory or out-of-range values."""
    rpt = risk.get("risk_per_trade_pct")
    dll = risk.get("daily_loss_limit_pct")
    mop = risk.get("max_open_positions")

    if rpt is not None and dll is not None:
        if rpt > dll:
            raise ImpossibleRiskError(
                f"risk_per_trade_pct ({rpt}) exceeds daily_loss_limit_pct ({dll}): "
                "a single trade would breach the daily limit."
            )
        if mop is not None and rpt * mop < dll * 0.0:
            # structural impossibility guard — currently the schema ceilings
            # (5% per trade, 20% daily) do allow any reasonable combination;
            # add more checks here as the risk engine matures.
            pass


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compile_candidate(candidate: dict) -> StrategySpec:
    """Compile an agent-proposed candidate into a StrategySpec.

    Raises:
        MissingParameterError: a required field is absent or ambiguous — ask the user.
        UnsupportedIndicatorError: expression references an unknown indicator.
        ImpossibleRiskError: risk values contradict each other or hard policy.
    """
    # Step 1: ask before building — never invent a missing parameter.
    questions = clarification_questions(candidate)
    if questions:
        # Report the first unanswered question as a MissingParameterError so the
        # caller has a typed error, but include ALL questions in the message so the
        # UI can surface the full set in one pass (B4 rule).
        all_q_text = " | ".join(questions)
        raise MissingParameterError(
            field="<multiple>",
            question=all_q_text,
        )

    # Step 2: check indicator allowlist before attempting model construction.
    entry_raw = candidate.get("entry", {})
    if entry_raw:
        _check_indicators(entry_raw)

    # Also check exit conditions if present.
    exit_raw = candidate.get("exit", {})
    if exit_raw and exit_raw.get("conditions"):
        _check_indicators(exit_raw)

    # Step 3: check risk consistency.
    risk_raw = candidate.get("risk", {})
    if risk_raw:
        _check_risk_consistency(risk_raw)

    # Step 4: validate bounded-exit invariant (anyOf in the schema).
    if exit_raw:
        has_stop = bool(exit_raw.get("stop_loss_pct"))
        has_time = bool(exit_raw.get("max_holding_minutes"))
        if not (has_stop or has_time):
            raise MissingParameterError(
                field="exit",
                question=(
                    "An unbounded strategy cannot be approved. "
                    "Provide stop_loss_pct or max_holding_minutes (or both)."
                ),
            )

    # Step 5: construct the Pydantic model — validation errors become typed failures.
    try:
        spec = StrategySpec.model_validate(candidate)
    except ValidationError as exc:
        # Surface the first validation error as a MissingParameterError so callers
        # get a consistent error type for missing/invalid fields.
        first = exc.errors()[0]
        field = ".".join(str(loc) for loc in first["loc"])
        raise MissingParameterError(field=field, question=first["msg"]) from exc

    return spec
