"""Model registry for the scanner.

The original scanner hardcoded six imports and six call signatures, each with
slightly different arguments (some take daily candles, some take scan_hour).
Adding a seventh meant editing four places and the display loop.

Here a model is a callable plus its metadata, and the scanner only ever sees
ModelResult. A model that needs the scan hour reads it from ScanContext.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .scanner import ScanContext


@dataclass(frozen=True)
class ModelResult:
    """One model's opinion about one bar.

    score is None when the model did not run at all (hard gate hit before
    scoring). That is different from score 0, which means "ran, found nothing" -
    the original collapsed both to 0 and the scoreboard could not tell a blocked
    model from a quiet one.
    """

    score: int | None
    direction: str | None = None  # "LONG" | "SHORT" | None
    stop: float | None = None
    target: float | None = None
    notes: str = ""
    blocked_by: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in (None, "LONG", "SHORT"):
            raise ValueError(f"direction must be LONG, SHORT or None: {self.direction!r}")
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError(f"score out of range: {self.score}")


class ScoreFn(Protocol):
    def __call__(self, ctx: ScanContext) -> ModelResult: ...


@dataclass(frozen=True)
class ScanModel:
    """A registered model.

    threshold is per-model on purpose: the original ran G/L/E at 55, H at 60,
    T at 70 (80 for shorts) and OMEGA at 95. A single global threshold cannot
    express "this model is only worth trading when it is very confident".

    directional_threshold overrides threshold for one side. Model T needed
    SHORT >= 80 while LONG stayed at 70, because its short win rate was half
    its long win rate. Encoding that as a rule beats a comment.

    evidence_ref is required: a model with no backtest reference cannot be
    registered. This is the gate that stops an idea becoming a live scorer
    without a RunManifest behind it.
    """

    key: str
    name: str
    threshold: int
    score_fn: ScoreFn
    evidence_ref: str
    directional_threshold: dict[str, int] = field(default_factory=dict)
    rank: int = 100  # tiebreak order when scores are within TIE_BAND; lower wins

    def threshold_for(self, direction: str | None) -> int:
        if direction and direction in self.directional_threshold:
            return self.directional_threshold[direction]
        return self.threshold


_MODELS: dict[str, ScanModel] = {}


def register_model(model: ScanModel) -> None:
    """Register a scoring model.

    Refuses a model with no evidence_ref. The scanner is a deterministic tool;
    what it scores must be traceable to a run, not to a conversation.
    """
    if not model.evidence_ref.strip():
        raise ValueError(
            f"model {model.key!r} has no evidence_ref - register a backtest "
            "run_id or RESULT.md path before it can score"
        )
    if model.key in _MODELS:
        raise ValueError(f"model {model.key!r} already registered")
    _MODELS[model.key] = model


def registered_models() -> list[ScanModel]:
    """Currently registered models, in registration order.

    Empty until real models land here. The scanner reports that state loudly
    rather than printing an empty scoreboard that looks like "no setups".
    """
    return list(_MODELS.values())


def _reset_registry_for_tests() -> None:
    _MODELS.clear()


#: Scores within this many points count as tied and fall back to ScanModel.rank.
TIE_BAND = 3


def select_best(
    results: list[tuple[ScanModel, ModelResult]],
) -> tuple[ScanModel, ModelResult] | None:
    """Pick the one trade to take, or None.

    Rules ported verbatim from the original tiebreaker:
      1. highest score wins;
      2. within TIE_BAND points, the better-evidenced model wins (rank);
      3. a LONG and a SHORT both qualifying means STAND ASIDE, never both.
    """
    qualified = [
        (m, r)
        for m, r in results
        if r.score is not None and r.direction and r.score >= m.threshold_for(r.direction)
    ]
    if not qualified:
        return None

    directions = {r.direction for _, r in qualified}
    if len(directions) > 1:
        return None  # conflict - caller renders "standing aside"

    top = max(r.score for _, r in qualified)  # type: ignore[type-var]
    contenders = [(m, r) for m, r in qualified if top - (r.score or 0) <= TIE_BAND]
    contenders.sort(key=lambda mr: (mr[0].rank, -(mr[1].score or 0)))
    return contenders[0]
