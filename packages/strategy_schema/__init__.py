"""StrategySpec: the immutable contract between AI and the deterministic engine (ADR-003).

Blueprint §22. This package owns the Pydantic models and the compiler that turns an
agent-proposed candidate into a validated, executable strategy representation.

Hard rule from AGENTS.md: *never invent an unspecified strategy parameter.* A missing
field raises; it does not default.
"""

from .errors import MissingParameterError, StrategyCompileError, UnsupportedIndicatorError
from .models import RiskPolicy, Rule, StrategySpec

__all__ = [
    "Rule", "RiskPolicy", "StrategySpec",
    "MissingParameterError", "UnsupportedIndicatorError", "StrategyCompileError",
]
