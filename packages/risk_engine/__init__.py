"""Deterministic risk enforcement. No AI in this package, ever.

Blueprint §24 and §35. This is the layer that says no. Every check here must be
callable without network, credentials or a model - so it can be exhaustively tested.
"""

from .kill_switch import KillSwitch
from .policies import HardLimits
from .pre_trade import PreTradeCheck, PreTradeResult

__all__ = ["HardLimits", "PreTradeCheck", "PreTradeResult", "KillSwitch"]
