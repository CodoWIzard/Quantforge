"""B5 and V3 - the board claims must stay true, not just have been true once.

B5: invalid/missing values become questions or errors, never invented defaults.
V3: three demos showing vague idea -> structured StrategySpec.

These run the real compiler over the committed corpus. No model, no network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
EXP = REPO / "experiments" / "002-strategy-compiler"

from packages.strategy_schema.compiler import (  # noqa: E402
    clarification_questions,
    compile_candidate,
)
from packages.strategy_schema.errors import StrategyCompileError  # noqa: E402

IDEAS = sorted((EXP / "ideas").glob("*.json"))
UNSAFE = sorted((EXP / "unsafe").glob("*.json"))

#: The §10 reference spec as an answered, structured candidate.
REFERENCE_SPEC = {
    "strategy_id": "btc-breakout", "version": 1,
    "market": "BTC-PERP", "timeframe": "5m", "direction": "long",
    "entry": {
        "conditions": [
            {"expression": "close > previous_4h_high", "lookback_bars": 48},
            {"expression": "volume > 1.5 * sma(volume, 20)", "lookback_bars": 20},
        ],
        "execute_at": "next_bar_open",
    },
    "exit": {"stop_loss_pct": 0.8, "take_profit_pct": 1.6, "max_holding_minutes": 180},
    "risk": {"risk_per_trade_pct": 0.5, "daily_loss_limit_pct": 1.5,
             "max_open_positions": 1},
}


# ------------------------------------------------------------------ B5

@pytest.mark.parametrize("path", IDEAS, ids=lambda p: p.stem)
def test_underspecified_ideas_produce_questions(path: Path):
    """The core B5 claim - a gap becomes a question, not a default."""
    doc = json.loads(path.read_text())
    if doc["completeness"] not in {"vague", "partial"}:
        pytest.skip("complete/edge ideas are covered separately")
    qs = clarification_questions({"raw_input": doc["raw_input"]})
    assert qs, f"{doc['id']} is under-specified but the compiler asked nothing"


@pytest.mark.parametrize("path", IDEAS, ids=lambda p: p.stem)
def test_never_compiles_with_open_questions(path: Path):
    """The invented-default failure, stated directly."""
    doc = json.loads(path.read_text())
    cand = {"raw_input": doc["raw_input"]}
    if not clarification_questions(cand):
        pytest.skip("nothing outstanding")
    with pytest.raises(StrategyCompileError):
        compile_candidate(cand)


@pytest.mark.parametrize("path", UNSAFE, ids=lambda p: p.stem)
def test_reject_class_never_compiles_silently(path: Path):
    doc = json.loads(path.read_text())
    if doc["expected_response"] != "REJECT":
        pytest.skip("not a refusal case")
    with pytest.raises(StrategyCompileError):
        compile_candidate({"raw_input": doc["request"]})


# ------------------------------------------------------------------ V3

def test_reference_spec_compiles_with_zero_questions():
    """Regression: _triggers_volume fired on the bare word 'volume'.

    That made the compiler interrogate its own reference spec and refuse a strategy
    that was complete by construction. Asking a question the user already answered
    is its own failure - it trains people to ignore the questions.
    """
    assert clarification_questions(REFERENCE_SPEC) == []
    spec = compile_candidate(REFERENCE_SPEC)
    assert spec.strategy_id == "btc-breakout"


def test_quantified_volume_asks_nothing():
    cand = dict(REFERENCE_SPEC)
    assert not any("volume" in q.lower() for q in clarification_questions(cand))


def test_vague_volume_still_asks():
    """The fix must not swing too far - unquantified volume is still a gap."""
    cand = json.loads(json.dumps(REFERENCE_SPEC))
    cand["entry"]["conditions"] = [{"expression": "volume is high", "lookback_bars": 20}]
    qs = clarification_questions(cand)
    assert any("volume" in q.lower() or "baseline" in q.lower() for q in qs)


def test_compiled_spec_is_hashable_for_reproducibility():
    """RunManifest pins strategy_hash to detect silent mutation."""
    h1 = compile_candidate(REFERENCE_SPEC).canonical_hash()
    h2 = compile_candidate(REFERENCE_SPEC).canonical_hash()
    assert h1 == h2 and len(h1) == 64


def test_hash_changes_when_a_rule_changes():
    """A hash that ignores the rules would defeat its own purpose."""
    other = json.loads(json.dumps(REFERENCE_SPEC))
    other["exit"]["stop_loss_pct"] = 1.9
    assert compile_candidate(REFERENCE_SPEC).canonical_hash() != \
        compile_candidate(other).canonical_hash()


def test_evidence_harnesses_are_committed_and_runnable():
    for name in ("run_b5_evidence.py", "run_v3_demos.py"):
        assert (EXP / name).is_file(), f"{name} missing"
