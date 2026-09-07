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


def compile_candidate(candidate: dict) -> object:
    """Compile an agent-proposed candidate into a StrategySpec.

    Raises:
        MissingParameterError: a required field is absent - ask the user.
        UnsupportedIndicatorError: expression references an unknown indicator.
        ImpossibleRiskError: risk values contradict each other or hard policy.
    """
    raise NotImplementedError("Experiment 002")


def clarification_questions(candidate: dict) -> list[str]:
    """Every question that must be answered before this candidate can compile.

    Returned all at once so the UI can ask them in a single guided pass instead of
    interrogating the user field by field.
    """
    raise NotImplementedError("Experiment 002")
