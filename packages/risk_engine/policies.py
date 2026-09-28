"""Hard limits that a strategy cannot raise and an agent cannot override.

§35 risk-control hierarchy, from outermost to innermost:

    strategy rules -> portfolio policy -> pre-trade validation
                   -> execution adapter -> runtime monitor -> emergency control

A StrategySpec may set values *tighter* than these. It may never set them looser.

Two ceilings, deliberately different (F-002)
--------------------------------------------
The pydantic model bounds (`risk_per_trade_pct <= 5`, `daily_loss_limit_pct <= 20`,
`max_open_positions <= 10`) are the SCHEMA envelope: the widest value the contract
can even represent. The numbers in this module are the OPERATIONAL ceiling: the
widest value the platform will accept. The schema envelope is deliberately looser
so that a breach arrives as a typed policy refusal naming the limit, instead of a
generic "input should be less than or equal to 2" from a validator — and so the
ceiling can be tightened here without a contract version bump.

Consequence: a value between the two is schema-legal and policy-illegal. That is
the intended state, not a bug. `check_risk_block` is what makes the difference
enforced rather than documented; before it existed the 2% limit appeared in no
code path at all and `risk_per_trade_pct: 3.0` with `daily_loss_limit_pct: 10.0`
compiled clean.

This module imports nothing from `strategy_schema`. It reports breaches as data;
the caller chooses the exception type. That keeps enforcement testable without
the compiler and stops the risk layer depending on the layer it polices.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class LimitBreach:
    """One requested value that exceeds one platform ceiling.

    Carries the ceiling and the attribute that owns it so an audit record (§34) can
    state which limit refused the strategy, not merely that something was refused.
    """

    field: str
    requested: float
    ceiling: float
    limit_attr: str

    def __str__(self) -> str:
        return (
            f"{self.field}={self.requested} exceeds the platform hard limit of "
            f"{self.ceiling} (HardLimits.{self.limit_attr})"
        )


class HardLimits:
    """Platform ceiling. Loaded from config, never from a model response."""

    max_risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    max_open_positions: int = 5
    max_orders_per_minute: int = 10
    max_data_staleness_seconds: int = 30

    # StrategySpec risk field -> the attribute on this class that caps it.
    # Only fields a StrategySpec can actually set belong here; the order and rate
    # limits are runtime concerns enforced by pre_trade, not by the compiler.
    _SPEC_FIELD_CEILINGS: Mapping[str, str] = {
        "risk_per_trade_pct": "max_risk_per_trade_pct",
        "daily_loss_limit_pct": "max_daily_loss_pct",
        "max_open_positions": "max_open_positions",
    }

    @classmethod
    def check_risk_block(cls, risk: Mapping[str, object]) -> list[LimitBreach]:
        """Every ceiling this risk block breaches.

        Returns ALL breaches, never the first: a strategy 50% over on two limits
        should not be reported as a single-limit problem, and the user should not
        have to resubmit once per limit to discover them.

        A field that is absent is not a breach — absence is the compiler's
        clarification concern (a missing value must be asked for, never defaulted
        to the ceiling). A non-numeric value is likewise left to schema validation;
        this function's contract is comparison, not type checking.
        """
        breaches: list[LimitBreach] = []
        for field, limit_attr in cls._SPEC_FIELD_CEILINGS.items():
            requested = risk.get(field)
            if requested is None or isinstance(requested, bool):
                continue
            if not isinstance(requested, (int, float)):
                continue
            ceiling = getattr(cls, limit_attr)
            if requested > ceiling:
                breaches.append(
                    LimitBreach(
                        field=field,
                        requested=requested,
                        ceiling=ceiling,
                        limit_attr=limit_attr,
                    )
                )
        return breaches
