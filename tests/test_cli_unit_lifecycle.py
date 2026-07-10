"""CLI contract tests for the unit-lifecycle verbs (ls / rm / mv).

Drives the new ``unit ls`` / ``unit rm`` / ``unit mv`` verbs through Typer's
``CliRunner`` and locks their coarse exit-code x stable JSON ``reason`` matrix
(mirroring tests/test_cli_contract.py). Fully offline: units and their
steering/progress are seeded directly through the store, so no git-identity
round-trip is needed. The ``repo`` fixture still configures a local identity for
parity with the other CLI contract tests.
"""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.cli.main import app
from dogen.core.models import (
    Effort,
    FileDigest,
    Generation,
    Intent,
    Provenance,
    Signoff,
)

runner = CliRunner()


def _payload(result) -> dict:
    """Parse the single JSON object line from a CLI result."""
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON object in output: {result.output!r}")


def _payload_array(result) -> list:
    """Parse the single JSON array line from a CLI result (``unit ls --json``)."""
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            return json.loads(stripped)
    raise AssertionError(f"no JSON array in output: {result.output!r}")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with a configured identity, used as the working dir."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ada@example.com"],
        check=True,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOGEN_PROVIDER", raising=False)
    return tmp_path


def _scaffold(root: Path, unit_id: str) -> FilesystemPlanningStore:
    """Scaffold a unit with a deterministic title and return the store."""
    store = FilesystemPlanningStore()
    store.scaffold_unit(
        unit_id,
        root=root,
        intent=Intent.reference,
        audience="devs",
        title=f"Title {unit_id}",
    )
    return store


def _seed_drafted(store: FilesystemPlanningStore, root: Path, unit_id: str) -> None:
    """Seed a steered + drafted unit plus its drafted docs output.

    PROV-04: the drafted lifecycle state is derived from the provenance record
    (a landed generation), not from a stored ``progress.yaml``.
    """
    store.write_provenance(
        Provenance(
            unit_id=unit_id,
            signoff=Signoff(
                author="Ada",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            generations=[
                Generation(
                    model="m",
                    model_version="v",
                    effort=Effort.medium,
                    tooling_version="0.0.0",
                    sdk="",
                    files=[FileDigest(path=f"docs/{unit_id}.md", sha256="ab12")],
                    run_id="r",
                    at="2026-01-01T00:00:01Z",
                    action="draft",
                )
            ],
        ),
        root=root,
    )
    store.write_draft(store.load_unit(unit_id, root=root), f"# {unit_id}\n", root=root)


# --------------------------------------------------------------------------- #
# unit ls
# --------------------------------------------------------------------------- #


def test_ls_empty_json_is_empty_array(repo):
    result = runner.invoke(app, ["unit", "ls", "--json"])
    assert result.exit_code == 0, result.output
    assert _payload_array(result) == []


def test_ls_json_lists_units_with_state(repo):
    store = _scaffold(repo, "a")
    _scaffold(repo, "b")
    _seed_drafted(store, repo, "b")

    result = runner.invoke(app, ["unit", "ls", "--json"])
    assert result.exit_code == 0, result.output
    array = _payload_array(result)
    assert len(array) == 2
    by_id = {obj["unit"]: obj for obj in array}
    assert by_id["a"]["state"] == "pending"
    assert by_id["b"]["state"] == "drafted"
    for obj in array:
        assert set(obj) == {"unit", "intent", "state", "title"}


def test_ls_plain_table_lists_units(repo):
    store = _scaffold(repo, "a")
    _scaffold(repo, "b")
    _seed_drafted(store, repo, "b")

    result = runner.invoke(app, ["unit", "ls"])
    assert result.exit_code == 0, result.output
    assert "a" in result.output
    assert "b" in result.output
    assert "pending" in result.output
    assert "drafted" in result.output


def test_ls_empty_plain_is_friendly(repo):
    result = runner.invoke(app, ["unit", "ls"])
    assert result.exit_code == 0, result.output
    assert "No units." in result.output


# --------------------------------------------------------------------------- #
# unit rm
# --------------------------------------------------------------------------- #


def test_rm_without_force_refuses_confirm_required(repo):
    _scaffold(repo, "u")
    result = runner.invoke(app, ["unit", "rm", "u", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "confirm_required"
    # The refusal must delete nothing.
    assert (repo / ".dogen" / "units" / "u").exists()


def test_rm_force_deletes_and_exits_ok(repo):
    store = _scaffold(repo, "u")
    _seed_drafted(store, repo, "u")
    assert (repo / "docs" / "u.md").exists()

    result = runner.invoke(app, ["unit", "rm", "u", "--force", "--json"])
    assert result.exit_code == 0, result.output
    assert not (repo / ".dogen" / "units" / "u").exists()
    assert not (repo / "docs" / "u.md").exists()


def test_rm_missing_unit_force_exits_not_found(repo):
    result = runner.invoke(app, ["unit", "rm", "ghost", "--force", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "unit_not_found"


# --------------------------------------------------------------------------- #
# unit mv
# --------------------------------------------------------------------------- #


def test_mv_success_exits_ok(repo):
    store = _scaffold(repo, "old")
    _seed_drafted(store, repo, "old")

    result = runner.invoke(app, ["unit", "mv", "old", "new", "--json"])
    assert result.exit_code == 0, result.output
    assert (repo / ".dogen" / "units" / "new").exists()
    assert not (repo / ".dogen" / "units" / "old").exists()


def test_mv_target_exists_exits_unit_exists(repo):
    _scaffold(repo, "old")
    _scaffold(repo, "taken")

    result = runner.invoke(app, ["unit", "mv", "old", "taken", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "unit_exists"


def test_mv_source_missing_exits_not_found(repo):
    result = runner.invoke(app, ["unit", "mv", "ghost", "new", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "unit_not_found"
