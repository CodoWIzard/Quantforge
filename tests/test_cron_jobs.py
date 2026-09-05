"""Contract tests for scheduled jobs.

The cron script exists in two places by necessity: the canonical copy in this
repo, and an installed copy under ~/.hermes/scripts/ (Hermes rejects absolute
script paths). These tests fail if the two drift apart.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"

ROOT = Path(__file__).resolve().parents[1]
REPO_COPY = ROOT / "infra" / "cron" / "quantforge_board_refresh.sh"
INSTALLED = Path("/root/.hermes/scripts/quantforge_board_refresh.sh")


def test_repo_copy_exists() -> None:
    assert REPO_COPY.is_file()


def test_script_is_valid_bash() -> None:
    r = subprocess.run([BASH, "-n", str(REPO_COPY)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_shellcheck_clean() -> None:
    sc = shutil.which("shellcheck") or "shellcheck"
    r = subprocess.run([sc, str(REPO_COPY)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


@pytest.mark.skipif(not INSTALLED.exists(), reason="installed copy absent")
def test_installed_copy_matches_repo() -> None:
    """Drift here means cron silently runs stale code."""
    assert INSTALLED.read_text() == REPO_COPY.read_text(), (
        "installed script differs from repo copy; "
        "run: cp infra/cron/quantforge_board_refresh.sh ~/.hermes/scripts/")


@pytest.mark.skipif(not INSTALLED.exists(), reason="installed copy absent")
def test_installed_copy_is_executable() -> None:
    assert INSTALLED.stat().st_mode & 0o111


def test_fails_loudly_when_repo_missing(tmp_path: Path) -> None:
    """A watchdog that fails silently is worthless."""
    broken = tmp_path / "broken.sh"
    broken.write_text(
        REPO_COPY.read_text().replace(
            "cd /root/projects/quantforge", "cd /nonexistent_path_xyz"))
    r = subprocess.run([BASH, str(broken)], capture_output=True, text=True)
    assert r.returncode != 0
    assert "repo missing" in r.stdout + r.stderr


def test_script_has_no_hardcoded_tokens() -> None:
    import re
    assert not re.search(r"MTU[0-9A-Za-z._-]{50,}", REPO_COPY.read_text())


def test_script_uses_project_venv() -> None:
    """System python lacks discord.py and the project deps."""
    assert ".venv/bin/python" in REPO_COPY.read_text()
