"""Every programmatic `hermes` invocation must name its profile explicitly (F-005).

Why this is a test and not a note: the backend supplies the operator's personal
trading context — MNQ1!, account size, unrelated bot projects — to prompts that never
mentioned any of it. Those facts are TRUE, so nothing downstream flags them, and they
are invisible in the transcript. The isolation boundary is the profile, and
`--ignore-user-config` does not close it.

Without `-p`, the six personas inherit whatever profile is sticky on the host. That can
change with no code change and no log line, which means a run is not reproducible and
"the model invented this field" cannot be distinguished from "the profile supplied it".

These tests read source text. They do NOT call a model: a live probe belongs in
Experiment 001, not in CI. See agents/evals/FAILURE_LOG.md F-005.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOTS = REPO / "services" / "discord-bots"

# Files that shell out to hermes as part of normal operation.
INVOKERS = [
    BOTS / "bots.py",
    BOTS / "builder.py",
]


def _existing(paths: list[Path]) -> list[Path]:
    return [p for p in paths if p.exists()]


@pytest.mark.parametrize("path", _existing(INVOKERS), ids=lambda p: p.name)
def test_hermes_invocations_pass_an_explicit_profile(path: Path):
    """A hermes argument list must contain '-p' or '--profile'.

    Asserted per-invocation rather than per-file so adding a new call site without the
    flag fails, even though existing call sites have it.
    """
    source = path.read_text()
    tree = ast.parse(source)

    invocations: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # create_subprocess_exec(HERMES, ...) / subprocess.run([HERMES, ...])
        # builder.py receives the binary as a parameter (`hermes_bin`) rather than a
        # module constant, so match either name — a detector that only knew one shape
        # would silently stop covering the write path.
        flat: list[ast.expr] = list(node.args)
        for arg in node.args:
            if isinstance(arg, (ast.List, ast.Tuple)):
                flat.extend(arg.elts)
        names = {a.id for a in flat if isinstance(a, ast.Name)}
        if names & {"HERMES", "hermes_bin"}:
            invocations.append(node)

    assert invocations, (
        f"{path.name} names HERMES but no call site was found — the detection in this "
        "test has gone stale and is no longer protecting anything"
    )

    for call in invocations:
        literals = []
        for arg in call.args:
            if isinstance(arg, (ast.List, ast.Tuple)):
                literals += [e.value for e in arg.elts if isinstance(e, ast.Constant)]
            elif isinstance(arg, ast.Constant):
                literals.append(arg.value)
        assert any(a in ("-p", "--profile") for a in literals if isinstance(a, str)), (
            f"{path.name}:{call.lineno} invokes hermes without -p. It will inherit "
            "whatever profile is sticky on the host and silently import that "
            "profile's personal context into a QuantForge prompt (F-005)."
        )


def test_the_profile_is_not_the_operators_personal_one():
    """`futures` and `default` both leak; they must never be the bots' profile.

    Named explicitly because the obvious first fix — pass `-p default` — is wrong: the
    default profile also volunteered MNQ1! and the repo path when probed.
    """
    for path in _existing(INVOKERS):
        source = path.read_text()
        for bad in ("-p futures", "-p default", '"futures"', "'futures'"):
            assert bad not in source, (
                f"{path.name} pins the profile to {bad!r}, which is verified to leak "
                "the operator's trading context (F-005)"
            )


def test_experiment_001_records_the_contamination_finding():
    """A green gate on 001 must not read as a licence to score the model layer.

    001's gate wording only covers authentication, logging and cost visibility — it
    never asked whether the call was clean. If this finding is dropped from the result,
    the next reader sees 'gate MET' and wires up the model harness.
    """
    result = (REPO / "experiments" / "001-model-call" / "RESULT.md").read_text()
    assert "F-005" in result
    assert "NO CONTEXT AVAILABLE" in result


def test_run_001_reads_cost_from_the_usage_file_not_a_dashboard():
    """`--usage-file` surfaces tokens and cost, so the manual-dashboard instruction is
    stale. Left in place it teaches the next person to hand-copy numbers a flag already
    produces — and hand-copied numbers are how fabricated metrics enter a report.

    Checks the instruction is gone, not the word: 'dashboard' legitimately appears in
    prose explaining why hand-copying is wrong.
    """
    script = (REPO / "experiments" / "001-model-call" / "run_001.py").read_text()
    assert "--usage-file" in script
    assert "Record manually from the model provider dashboard" not in script
    # the cost gate must actually read the file, not just pass the flag
    assert "_read_usage" in script


def test_run_001_probes_the_backend_for_contamination():
    """A green 001 must mean the backend was clean, not merely that it answered.

    Without this the experiment can pass on a contaminated profile and the next person
    reads 'gate MET' as licence to score the model layer (F-005).
    """
    script = (REPO / "experiments" / "001-model-call" / "run_001.py").read_text()
    assert "UNKNOWN" in script, "no contamination probe assertion"
    assert "_probe_contamination" in script


def test_builder_requires_the_profile_as_a_keyword_argument():
    """`hermes_profile` must have no default.

    A default would let a new call site omit it and inherit whatever the default names
    — the failure would surface as odd model behaviour, not as a missing argument.
    """
    import ast

    tree = ast.parse((BOTS / "builder.py").read_text())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "build"
    )
    names = [a.arg for a in fn.args.kwonlyargs]
    assert "hermes_profile" in names, "builder.build() takes no hermes_profile"
    idx = names.index("hermes_profile")
    assert fn.args.kw_defaults[idx] is None, (
        "hermes_profile has a default; a new call site could silently omit it"
    )


def test_the_default_profile_is_the_dedicated_one():
    """Defaults matter more than the flag: an unset env var is the common path."""
    source = (BOTS / "bots.py").read_text()
    assert '"quantforge"' in source or "'quantforge'" in source, (
        "no dedicated profile named as the default"
    )


def test_no_invocation_relies_on_ignore_user_config_for_isolation():
    """It reads like the right switch and is not: the probe leaked MORE with it set.

    A future reader reaching for it instead of `-p` would believe the leak was closed.
    """
    for path in _existing(INVOKERS):
        source = path.read_text()
        if "--ignore-user-config" in source:
            assert re.search(r"-p\b|--profile", source), (
                f"{path.name} uses --ignore-user-config without -p. That flag does not "
                "isolate profile context (F-005)"
            )
