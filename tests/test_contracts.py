"""The data contracts are real files with real rules - assert them.

These run today with no dependencies beyond the stdlib. They exist because
data-contracts/ is the interface both AIOS environments build against: a typo here
propagates into two codebases before anyone notices.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CONTRACTS = Path(__file__).resolve().parent.parent / "data-contracts"
SCHEMAS = sorted(CONTRACTS.glob("*.schema.json"))


def test_contract_directory_is_populated():
    assert len(SCHEMAS) == 4, f"expected 4 JSON schemas, found {[s.name for s in SCHEMAS]}"


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda p: p.name)
def test_schema_is_valid_json(path: Path):
    json.loads(path.read_text())


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda p: p.name)
def test_schema_declares_id_and_title(path: Path):
    doc = json.loads(path.read_text())
    assert doc.get("$id", "").startswith("https://quantforge.dev/contracts/v1/")
    assert doc.get("title")
    assert doc.get("description"), (
        "a contract without a description is a contract nobody can follow"
    )


def _spec() -> dict:
    return json.loads((CONTRACTS / "strategy-spec.schema.json").read_text())


def test_strategyspec_forbids_extra_properties():
    """ADR-003 + AGENTS.md: no silently accepted unknown field."""
    assert _spec()["additionalProperties"] is False


def test_strategyspec_requires_risk_block():
    """§35: a strategy without a risk policy can never be approved."""
    assert "risk" in _spec()["required"]


def test_strategyspec_scope_is_btc_eth_only():
    """ADR-001 restricts the internship to BTC/ETH perpetuals on one exchange."""
    assert set(_spec()["properties"]["market"]["enum"]) == {"BTC-PERP", "ETH-PERP"}


def test_strategyspec_timeframes_exclude_hft():
    """§6: intraday 1m-15m. Sub-minute timeframes are an explicit non-goal."""
    tfs = set(_spec()["properties"]["timeframe"]["enum"])
    assert tfs == {"1m", "5m", "15m"}
    assert not any(t.endswith("s") for t in tfs)


def test_strategyspec_requires_a_bounded_exit():
    """An unbounded strategy has no risk profile - one of stop or max-hold is mandatory."""
    exit_block = _spec()["properties"]["exit"]
    required_sets = [set(o["required"]) for o in exit_block["anyOf"]]
    assert {"stop_loss_pct"} in required_sets
    assert {"max_holding_minutes"} in required_sets


def test_risk_values_are_bounded():
    """Hard ceilings live in the schema so an agent cannot propose 50% per trade."""
    risk = _spec()["properties"]["risk"]["properties"]
    assert risk["risk_per_trade_pct"]["maximum"] <= 5
    assert risk["daily_loss_limit_pct"]["maximum"] <= 20


def test_run_manifest_captures_reproducibility_inputs():
    """AGENTS.md: every backtest result must be reproducible from its RunManifest."""
    doc = json.loads((CONTRACTS / "run-manifest.schema.json").read_text())
    required = set(doc["required"])
    for field in ("strategy_version", "dataset", "fee_model", "slippage_model", "engine_version"):
        assert field in required, f"RunManifest must pin {field}"


def test_manifest_gap_policy_forbids_silent_interpolation():
    """§18: interpolating a gap silently is a named failure mode."""
    doc = json.loads((CONTRACTS / "run-manifest.schema.json").read_text())
    policy = doc["properties"]["dataset"]["properties"]["gap_policy"]["enum"]
    assert set(policy) == {"fail", "mark_and_exclude"}
    assert "interpolate" not in " ".join(policy)


def test_backtest_result_keeps_sharpe_nullable():
    """Below a meaningful sample, a ratio is noise - the schema must allow null."""
    doc = json.loads((CONTRACTS / "backtest-result.schema.json").read_text())
    assert "null" in doc["properties"]["metrics"]["properties"]["sharpe"]["type"]


def test_backtest_result_carries_engine_warnings():
    """§18: the engine's own red flags must survive to the report layer."""
    doc = json.loads((CONTRACTS / "backtest-result.schema.json").read_text())
    assert "warnings" in doc["properties"]


def test_market_event_shared_by_backtest_and_live():
    """One event shape for replay and live, so paper cannot silently diverge."""
    doc = json.loads((CONTRACTS / "market-event.schema.json").read_text())
    assert set(doc["required"]) >= {"event_type", "symbol", "ts_utc", "received_utc"}
