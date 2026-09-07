"""Pydantic models mirroring data-contracts/strategy-spec.schema.json.

The JSON Schema is the cross-language contract; these models are the Python binding.
tests/test_contracts.py asserts the two stay in agreement - if you edit one, edit both.

Blueprint §10 (example spec) and §22 (minimal design).
"""

from __future__ import annotations

from typing import Literal

# NOTE: pydantic is not yet a project dependency. Add it in the PR that implements
# Experiment 002, together with these models. Declared here as the agreed shape.

Market = Literal["BTC-PERP", "ETH-PERP"]          # ADR-001
Timeframe = Literal["1m", "5m", "15m"]            # §6 - intraday, no HFT
Direction = Literal["long", "short", "both"]
ExecuteAt = Literal["next_bar_open", "current_bar_close"]

#: Indicators the compiler will accept. Anything else raises UnsupportedIndicatorError
#: rather than being passed through to eval. Extend deliberately, with tests.
SUPPORTED_INDICATORS: frozenset[str] = frozenset({
    "sma", "ema", "rsi", "atr", "high", "low", "close", "open", "volume",
    "previous_4h_high", "previous_4h_low",
})


class Rule:
    """One boolean condition, e.g. ``close > previous_4h_high``.

    ``lookback_bars`` is the declared warmup. The backtester asserts that no signal
    fires before that index, which is one half of the no-look-ahead guarantee (§23).
    """

    expression: str
    lookback_bars: int


class RiskPolicy:
    """Portfolio-policy layer of §35.

    The risk engine enforces these. A Risk Reviewer agent may *explain* them and propose
    tighter values, but §15 forbids it from overriding a hard policy.
    """

    risk_per_trade_pct: float
    daily_loss_limit_pct: float
    max_open_positions: int
    max_notional_usd: float | None


class StrategySpec:
    """Versioned, immutable strategy definition.

    Immutability is the point (ADR-003): a running deployment loads one version and
    cannot be mutated in memory. A change means a new version, re-validation and a new
    approval (§11).
    """

    strategy_id: str
    version: int
    market: Market
    timeframe: Timeframe
    direction: Direction
    # entry / exit / risk per the JSON Schema

    def canonical_hash(self) -> str:
        """sha256 of the canonical JSON form, recorded in the RunManifest.

        Detects silent mutation between approval and execution.
        """
        raise NotImplementedError("Experiment 002")
