"""Strategy compiler — blueprint Appendix E minimum test catalogue.

Experiment 002 B3: these tests verify the three implemented behaviours.
"""

from __future__ import annotations

import pytest

from packages.strategy_schema.compiler import clarification_questions, compile_candidate
from packages.strategy_schema.errors import (
    ImpossibleRiskError,
    MissingParameterError,
    UnsupportedIndicatorError,
)
from packages.strategy_schema.models import StrategySpec

# ---------------------------------------------------------------------------
# Minimal valid candidate — extend per test as needed
# ---------------------------------------------------------------------------

_VALID = {
    "strategy_id": "btc-breakout-v1",
    "version": 1,
    "market": "BTC-PERP",
    "timeframe": "5m",
    "direction": "long",
    "entry": {
        "conditions": [
            {"expression": "close > previous_4h_high", "lookback_bars": 20}
        ],
        "execute_at": "next_bar_open",
    },
    "exit": {
        "stop_loss_pct": 1.0,
        "take_profit_pct": 2.0,
    },
    "risk": {
        "risk_per_trade_pct": 1.0,
        "daily_loss_limit_pct": 3.0,
        "max_open_positions": 2,
    },
}


def _merge(base: dict, patch: dict) -> dict:
    """Shallow-merge patch into a deep copy of base."""
    import copy
    result = copy.deepcopy(base)
    result.update(patch)
    return result


# ---------------------------------------------------------------------------
# test_missing_parameter_raises_and_asks
# ---------------------------------------------------------------------------

def test_missing_parameter_raises_and_asks():
    """A missing threshold produces a question, never a default value."""
    candidate = {
        "strategy_id": "btc-rsi",
        "version": 1,
        "market": "BTC-PERP",
        "direction": "long",
        # no timeframe — should trigger timeframe clarification rule
        "entry": {
            "conditions": [{"expression": "rsi cross 30", "lookback_bars": 14}],
            "execute_at": "next_bar_open",
        },
        "exit": {"stop_loss_pct": 1.0},
        "risk": {
            "risk_per_trade_pct": 1.0,
            "daily_loss_limit_pct": 3.0,
            "max_open_positions": 1,
        },
    }
    questions = clarification_questions(candidate)
    # Must have questions — no timeframe + bare "rsi" without period triggers rules
    assert len(questions) > 0, "Expected clarification questions for missing timeframe"

    with pytest.raises(MissingParameterError) as exc_info:
        compile_candidate(candidate)

    err = exc_info.value
    # field is set, question is non-empty and contains the outstanding question text
    assert err.field
    assert err.question
    # Must NOT have returned a default — the exception proves it
    # (if it returned a StrategySpec, no exception would be raised)


# ---------------------------------------------------------------------------
# test_invalid_indicator_rejected
# ---------------------------------------------------------------------------

def test_invalid_indicator_rejected():
    """An expression outside SUPPORTED_INDICATORS is rejected, not evaluated."""
    candidate = _merge(_VALID, {
        "entry": {
            "conditions": [
                {"expression": "macd_histogram > 0", "lookback_bars": 26}
            ],
            "execute_at": "next_bar_open",
        }
    })
    with pytest.raises(UnsupportedIndicatorError) as exc_info:
        compile_candidate(candidate)

    assert "macd_histogram" in str(exc_info.value)


# ---------------------------------------------------------------------------
# test_impossible_risk_values_rejected
# ---------------------------------------------------------------------------

def test_impossible_risk_values_rejected():
    """risk_per_trade > daily_loss_limit is contradictory and must fail."""
    candidate = _merge(_VALID, {
        "risk": {
            "risk_per_trade_pct": 4.0,   # 4% per trade
            "daily_loss_limit_pct": 2.0,  # but only 2% daily limit — impossible
            "max_open_positions": 2,
        }
    })
    with pytest.raises(ImpossibleRiskError):
        compile_candidate(candidate)


# ---------------------------------------------------------------------------
# test_same_input_same_spec
# ---------------------------------------------------------------------------

def test_same_input_same_spec():
    """Deterministic: identical candidate compiles to an identical spec hash."""
    spec_a = compile_candidate(_VALID)
    spec_b = compile_candidate(_VALID)

    assert isinstance(spec_a, StrategySpec)
    assert isinstance(spec_b, StrategySpec)
    assert spec_a.canonical_hash() == spec_b.canonical_hash()


# ---------------------------------------------------------------------------
# test_clarification_questions_returns_all_at_once
# ---------------------------------------------------------------------------

def test_clarification_questions_returns_all_at_once():
    """All outstanding questions come back in one call, never one at a time."""
    # Candidate that triggers multiple rules: no market, no timeframe, no risk
    candidate = {
        "strategy_id": "eth-breakout",
        "version": 1,
        # no market, no timeframe, no risk
        "direction": "long",
        "entry": {
            "conditions": [
                {"expression": "close > previous_4h_high", "lookback_bars": 20}
            ],
            "execute_at": "next_bar_open",
        },
        "exit": {"stop_loss_pct": 1.0},
    }
    questions = clarification_questions(candidate)
    # market rule asks 2 questions, timeframe asks 3, risk asks 4 = at least 9
    assert len(questions) >= 5, (
        f"Expected at least 5 questions for market+timeframe+risk gaps, got {len(questions)}"
    )


# ---------------------------------------------------------------------------
# test_valid_candidate_compiles_to_strategyspec
# ---------------------------------------------------------------------------

def test_valid_candidate_compiles_to_strategyspec():
    """A fully specified candidate compiles successfully."""
    spec = compile_candidate(_VALID)
    assert isinstance(spec, StrategySpec)
    assert spec.strategy_id == "btc-breakout-v1"
    assert spec.market == "BTC-PERP"
    assert spec.timeframe == "5m"
    assert spec.direction == "long"
    assert spec.risk.risk_per_trade_pct == 1.0
    # canonical_hash is deterministic and non-empty
    h = spec.canonical_hash()
    assert len(h) == 64  # sha256 hex
