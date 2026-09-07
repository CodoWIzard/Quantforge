"""Typed failures for strategy compilation.

Each maps to a §18 evaluation case. They exist as distinct types so the clarification
agent can react differently to "you forgot to tell me X" versus "X is not supported".
"""


class StrategyCompileError(Exception):
    """Base: the candidate cannot become an executable strategy."""


class MissingParameterError(StrategyCompileError):
    """A required value was absent.

    The correct response is to ASK the user, never to substitute a plausible default.
    §18: inventing "1.5x volume" without confirmation is the canonical failure.
    """

    def __init__(self, field: str, question: str) -> None:
        self.field = field
        self.question = question
        super().__init__(f"missing required parameter {field!r}: ask - {question}")


class UnsupportedIndicatorError(StrategyCompileError):
    """The expression references something outside the supported allowlist."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"indicator {name!r} is not in the supported allowlist")


class ImpossibleRiskError(StrategyCompileError):
    """Risk values that are internally contradictory or outside hard policy bounds."""
