"""Pydantic models mirroring data-contracts/strategy-spec.schema.json.

The JSON Schema is the cross-language contract; these models are the Python binding.
tests/test_contracts.py asserts the two stay in agreement - if you edit one, edit both.

Blueprint §10 (example spec) and §22 (minimal design).
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class Rule(BaseModel):
    """One boolean condition, e.g. ``close > previous_4h_high``.

    ``lookback_bars`` is the declared warmup. The backtester asserts that no signal
    fires before that index, which is one half of the no-look-ahead guarantee (§23).
    """

    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1)
    lookback_bars: int | None = Field(default=None, ge=0)


class RiskPolicy(BaseModel):
    """Portfolio-policy layer of §35.

    The risk engine enforces these. A Risk Reviewer agent may *explain* them and propose
    tighter values, but §15 forbids it from overriding a hard policy.
    """

    model_config = ConfigDict(extra="forbid")

    risk_per_trade_pct: float = Field(gt=0, le=5)
    daily_loss_limit_pct: float = Field(gt=0, le=20)
    max_open_positions: int = Field(ge=1, le=10)
    max_notional_usd: float | None = Field(default=None, gt=0)


class EntryBlock(BaseModel):
    """Entry conditions and execution timing."""

    model_config = ConfigDict(extra="forbid")

    conditions: list[Rule] = Field(min_length=1)
    execute_at: ExecuteAt


class ExitBlock(BaseModel):
    """Exit rules — at least one bounded exit (stop or max_holding_minutes) is mandatory.

    Schema uses anyOf to enforce this. We validate the constraint in compile_candidate.
    """

    model_config = ConfigDict(extra="forbid")

    stop_loss_pct: float | None = Field(default=None, gt=0, le=50)
    take_profit_pct: float | None = Field(default=None, gt=0, le=100)
    max_holding_minutes: int | None = Field(default=None, ge=1, le=10080)
    conditions: list[Rule] = Field(default_factory=list)


class SpecMetadata(BaseModel):
    """Optional audit trail fields (§9 step 1)."""

    model_config = ConfigDict(extra="forbid")

    created_by: str | None = None
    source_hypothesis: str | None = None
    clarifications: list[dict] = Field(default_factory=list)


class StrategySpec(BaseModel):
    """Versioned, immutable strategy definition.

    Immutability is the point (ADR-003): a running deployment loads one version and
    cannot be mutated in memory. A change means a new version, re-validation and a new
    approval (§11).
    """

    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    version: int = Field(ge=1)
    market: Market
    timeframe: Timeframe
    direction: Direction
    entry: EntryBlock
    exit: ExitBlock
    risk: RiskPolicy
    metadata: SpecMetadata | None = None

    def canonical_hash(self) -> str:
        """sha256 of the canonical JSON form, recorded in the RunManifest.

        Detects silent mutation between approval and execution.
        Keys sorted for stability; metadata excluded (it does not affect behaviour).
        """
        payload = self.model_dump(exclude={"metadata"}, mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
