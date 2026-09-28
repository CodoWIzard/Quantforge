"""Platform hard limits — the one part of the risk engine that runs today.

`tests/test_risk_engine.py` stays blanket-xfail: pre-trade validation, the daily-loss
halt and the kill switch are Weeks 13-14 and genuinely unimplemented. The policy
ceiling is not. Keeping it here means a real check is never reported as xfail, and
the unimplemented runtime checks are never reported as covered.

Closes F-002. Read `agents/evals/FAILURE_LOG.md` before changing the numbers: the gap
between these ceilings and the pydantic bounds is deliberate, not an inconsistency.
"""

from __future__ import annotations

import pytest

from packages.risk_engine import HardLimits, LimitBreach
from packages.strategy_schema.compiler import _check_risk_consistency
from packages.strategy_schema.errors import ImpossibleRiskError
from packages.strategy_schema.models import RiskPolicy

MECHANISM = "platform hard limit"


# ---------------------------------------------------------------------------
# the ceiling itself
# ---------------------------------------------------------------------------

def test_hard_limits_are_the_documented_numbers():
    """The ceilings are a contract, not a tuning knob.

    Pinned so that loosening one is a visible, reviewable diff rather than a quiet
    edit — the whole of F-002 was a limit nobody could see was missing.
    """
    assert HardLimits.max_risk_per_trade_pct == 2.0
    assert HardLimits.max_daily_loss_pct == 5.0
    assert HardLimits.max_open_positions == 5


def test_a_compliant_block_has_no_breaches():
    """Negative control. If this cannot pass, every other assertion here is vacuous."""
    risk = {
        "risk_per_trade_pct": 1.0,
        "daily_loss_limit_pct": 3.0,
        "max_open_positions": 3,
    }
    assert HardLimits.check_risk_block(risk) == []


def test_values_exactly_at_the_ceiling_are_allowed():
    """The limit is a maximum, not an exclusive bound — 2.0% must compile."""
    risk = {
        "risk_per_trade_pct": 2.0,
        "daily_loss_limit_pct": 5.0,
        "max_open_positions": 5,
    }
    assert HardLimits.check_risk_block(risk) == []


@pytest.mark.parametrize(
    "field,value,limit_attr",
    [
        ("risk_per_trade_pct", 2.01, "max_risk_per_trade_pct"),
        ("risk_per_trade_pct", 3.0, "max_risk_per_trade_pct"),
        ("risk_per_trade_pct", 50.0, "max_risk_per_trade_pct"),
        ("daily_loss_limit_pct", 6.0, "max_daily_loss_pct"),
        ("max_open_positions", 7, "max_open_positions"),
    ],
)
def test_each_ceiling_is_enforced_and_names_itself(field, value, limit_attr):
    """A breach identifies the limit that refused it.

    §34 audits the reason, not just the refusal: "risk too high" cannot be acted on,
    "exceeds HardLimits.max_risk_per_trade_pct" can.
    """
    risk = {
        "risk_per_trade_pct": 1.0,
        "daily_loss_limit_pct": 3.0,
        "max_open_positions": 3,
        field: value,
    }
    breaches = HardLimits.check_risk_block(risk)
    assert len(breaches) == 1
    (breach,) = breaches
    assert isinstance(breach, LimitBreach)
    assert breach.field == field
    assert breach.requested == value
    assert breach.limit_attr == limit_attr
    assert limit_attr in str(breach)


def test_every_breach_is_reported_not_just_the_first():
    """A strategy over on three limits must not look like a one-limit problem.

    Otherwise the user fixes one value, resubmits, and discovers the next — three
    round trips to learn what one refusal could have said.
    """
    risk = {
        "risk_per_trade_pct": 4.0,
        "daily_loss_limit_pct": 15.0,
        "max_open_positions": 9,
    }
    fields = {b.field for b in HardLimits.check_risk_block(risk)}
    assert fields == {
        "risk_per_trade_pct",
        "daily_loss_limit_pct",
        "max_open_positions",
    }


def test_absent_field_is_not_a_breach():
    """Absence is the compiler's clarification concern.

    Treating a missing value as a breach would report "exceeds 2%" for a field the
    user never set; defaulting it to the ceiling would invent a parameter (§18).
    """
    assert HardLimits.check_risk_block({}) == []
    assert HardLimits.check_risk_block({"daily_loss_limit_pct": 3.0}) == []


def test_non_numeric_and_bool_values_are_left_to_schema_validation():
    """This function compares; it does not type check. Booleans are ints in Python
    and `True > 2.0` is False anyway — excluded explicitly so the intent is not
    mistaken for an oversight."""
    assert HardLimits.check_risk_block({"risk_per_trade_pct": "lots"}) == []
    assert HardLimits.check_risk_block({"risk_per_trade_pct": None}) == []
    assert HardLimits.check_risk_block({"max_open_positions": True}) == []


def test_risk_engine_does_not_import_the_layer_it_polices():
    """The layer that says no must not depend on the layer it judges (§35).

    Also keeps `policies` importable with no third-party dependency, so the ceiling
    can be enforced in contexts where pydantic is not installed. Asserted over the
    parsed import statements, not the source text — the docstring legitimately
    discusses both names.
    """
    import ast
    import pathlib
    import sys

    import packages.risk_engine.policies as policies

    tree = ast.parse(pathlib.Path(policies.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "packages" not in imported
    assert "pydantic" not in imported
    # stdlib only — no third-party dependency, so the ceiling is enforceable anywhere
    assert imported <= set(sys.stdlib_module_names), imported


# ---------------------------------------------------------------------------
# the compiler actually consults it — F-002's exact reproduction table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "risk,expect_reject,note",
    [
        ({"risk_per_trade_pct": 0.5, "daily_loss_limit_pct": 1.5}, False, "compliant"),
        ({"risk_per_trade_pct": 50.0, "daily_loss_limit_pct": 1.5}, True, "far over"),
        ({"risk_per_trade_pct": 3.0, "daily_loss_limit_pct": 1.5}, True,
         "over, relational also fires"),
        # The row that compiled before F-002 was fixed: 50% over the ceiling, and the
        # relational rule cannot fire because the daily limit is generous.
        ({"risk_per_trade_pct": 3.0, "daily_loss_limit_pct": 10.0}, True, "F-002 regression row"),
        ({"risk_per_trade_pct": 1.0, "daily_loss_limit_pct": 6.0}, True, "daily ceiling alone"),
    ],
)
def test_compiler_enforces_the_ceiling(risk, expect_reject, note):
    if not expect_reject:
        _check_risk_consistency(risk)
        return
    with pytest.raises(ImpossibleRiskError) as exc:
        _check_risk_consistency(risk)
    assert MECHANISM in str(exc.value), f"{note}: refused, but not by the policy check"


def test_absolute_check_runs_before_the_relational_one():
    """Ordering is the fix, not an implementation detail.

    `risk 3.0 / daily 1.5` breaches the ceiling AND is relationally absurd. Whichever
    rule reports it is the one a reader will believe is enforcing the limit — so the
    owner of the rule must answer first. Reversed, F-002 becomes invisible again.
    """
    with pytest.raises(ImpossibleRiskError) as exc:
        _check_risk_consistency({"risk_per_trade_pct": 3.0, "daily_loss_limit_pct": 1.5})
    assert MECHANISM in str(exc.value)
    assert "breach the daily limit" not in str(exc.value)


def test_relational_check_is_not_dead_code():
    """Both values under their ceilings, still mutually absurd.

    Guards against "simplifying" the relational rule away now that the absolute one
    catches the headline cases.
    """
    with pytest.raises(ImpossibleRiskError) as exc:
        _check_risk_consistency({"risk_per_trade_pct": 1.5, "daily_loss_limit_pct": 1.0})
    assert MECHANISM not in str(exc.value)
    assert "breach the daily limit" in str(exc.value)


def test_schema_envelope_is_deliberately_looser_than_the_policy_ceiling():
    """The two-ceiling design, asserted so it is not "tidied" into one.

    3.0% must remain schema-VALID and policy-INVALID. If pydantic is tightened to
    le=2 the breach surfaces as a generic validator message that names no policy,
    and `LimitBreach` stops being reachable from the compiler.
    """
    RiskPolicy(risk_per_trade_pct=3.0, daily_loss_limit_pct=10.0, max_open_positions=3)
    assert HardLimits.check_risk_block(
        {"risk_per_trade_pct": 3.0, "daily_loss_limit_pct": 10.0}
    )
