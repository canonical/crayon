"""The skills install flow (Q7): staging, manifest, drift, auto-discovery."""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.skills_install import (
    HARNESS_ROOTS,
    discover_harnesses,
    install,
    status,
    update,
)
from dogen.cli.main import app

runner = CliRunner()
_CANONICAL = Path(__file__).resolve().parents[1] / "skills"


@pytest.fixture
def target(tmp_path, monkeypatch):
    """A tmp target repo with a .claude/ dir, cwd set."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".claude").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_install_stages_byte_identical_copies(target):
    record = install(target, "claude", source=_CANONICAL, at="2026-07-03T00:00:00Z")
    staged = target / HARNESS_ROOTS["claude"]
    for rel in (
        "dogen-plan/SKILL.md",
        "dogen-write/SKILL.md",
        "dogen-review/SKILL.md",
        "dogen-write/references/provider-branch.md",
        "README.md",
        "LICENSE",
    ):
        assert (staged / rel).read_bytes() == (_CANONICAL / rel).read_bytes()
    assert record["sha256"]
    assert record["path"] == ".claude/skills"


def test_status_reports_ok_then_drift_then_update_heals(target):
    install(target, "claude", source=_CANONICAL, at="t0")
    rows = status(target, source=_CANONICAL)
    assert [r["state"] for r in rows] == ["ok"]
    # Mutate the staged copy -> drifted.
    staged_skill = target / HARNESS_ROOTS["claude"] / "dogen-plan" / "SKILL.md"
    staged_skill.write_text(
        staged_skill.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8"
    )
    rows = status(target, source=_CANONICAL)
    assert [r["state"] for r in rows] == ["drifted"]
    # Update re-stages from canonical.
    update(target, source=_CANONICAL, at="t1")
    rows = status(target, source=_CANONICAL)
    assert [r["state"] for r in rows] == ["ok"]


def test_discovery_detects_present_harness_dirs(target):
    assert discover_harnesses(target) == ["claude"]
    (target / ".github").mkdir()
    assert discover_harnesses(target) == ["claude", "copilot"]
    (target / ".opencode").mkdir()
    assert discover_harnesses(target) == ["claude", "copilot", "opencode"]


def test_update_relocates_a_stale_recorded_path(target):
    """A manifest recording a superseded root is cleaned up and re-staged.

    Round-2 forensics: skills staged at ``.agents/skills`` were invisible to
    opencode (it discovers ``.opencode/skills`` only), and the hand-fix left a
    stale manifest behind. ``update`` must move the install to the current
    table root and remove the dogen-owned family from the old one.
    """
    install(target, "opencode", source=_CANONICAL, at="t0")
    manifest_path = target / ".dogen" / "skills-install.yaml"
    stale_root = target / ".agents" / "skills"
    current_root = target / HARNESS_ROOTS["opencode"]
    # Simulate the pre-fix layout: family staged under .agents/skills and the
    # manifest recording that path.
    stale_root.parent.mkdir()
    current_root.rename(stale_root)
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            HARNESS_ROOTS["opencode"], ".agents/skills"
        ),
        encoding="utf-8",
    )
    update(target, source=_CANONICAL, at="t1")
    assert (current_root / "dogen-plan" / "SKILL.md").is_file()
    assert not stale_root.exists()
    assert ".agents/skills" not in manifest_path.read_text(encoding="utf-8")
    rows = status(target, source=_CANONICAL)
    assert [(r["harness"], r["state"]) for r in rows] == [("opencode", "ok")]


def test_cli_install_auto_detects_and_records_manifest(target):
    result = runner.invoke(
        app, ["skills", "install", "--from", str(_CANONICAL), "--json"]
    )
    assert result.exit_code == 0, result.output
    records = json.loads(result.output.splitlines()[-1])
    assert [r["harness"] for r in records] == ["claude"]
    assert (target / ".dogen" / "skills-install.yaml").is_file()
    result = runner.invoke(
        app, ["skills", "status", "--from", str(_CANONICAL), "--json"]
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output.splitlines()[-1])
    assert [r["state"] for r in rows] == ["ok"]


def test_cli_install_no_harness_detected_is_bad_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["skills", "install", "--from", str(_CANONICAL)])
    assert result.exit_code == 2


def test_cli_install_unknown_harness_is_bad_input(target):
    result = runner.invoke(
        app,
        ["skills", "install", "--harness", "banana", "--from", str(_CANONICAL)],
    )
    assert result.exit_code == 2
