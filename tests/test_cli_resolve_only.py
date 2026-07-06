"""``draft --resolve-only``: zero-side-effect provider resolution (D-07/D-06).

Locks the affordance the Phase-4 skill calls first to branch driver-vs-passenger:
``dogen draft U --resolve-only`` runs only the OFFLINE selection and prints the
resolved provider (plain + ``--json``) with **zero side effects** — no gate, no
generation, no ``.dogen`` provenance/progress, no ``docs/`` write (T-03-02). Also
locks the D-06 precedence: ``--provider`` flag > ``DOGEN_PROVIDER`` env > ``auto``.
Fully offline — an explicit ``mock`` / a monkeypatched capability probe, no token,
no network.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.cli.main import app
from dogen.core.models import Intent

runner = CliRunner()


@pytest.fixture
def clean_env(monkeypatch):
    """Clear the provider env vars so each test controls resolution explicitly."""
    for var in (
        "DOGEN_PROVIDER",
        "COPILOT_SDK_AUTH_TOKEN",
        "DOGEN_DISABLE_COPILOT",
    ):
        monkeypatch.delenv(var, raising=False)


def _snapshot(root: Path) -> set[Path]:
    """Return the set of every existing path under the tmp root (for diffing)."""
    return set(root.rglob("*"))


def test_resolve_only_plain_prints_provider_with_zero_side_effects(
    tmp_path, monkeypatch, clean_env
):
    # --resolve-only prints the resolved provider and writes NOTHING: with no unit
    # scaffolded, no .dogen or docs/ tree is created at all.
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["draft", "u", "--resolve-only", "--provider", "mock"])
    assert result.exit_code == 0, result.output
    assert "mock" in result.output
    assert not (tmp_path / ".dogen").exists()
    assert not (tmp_path / "docs").exists()


def test_resolve_only_leaves_an_existing_unit_dir_unchanged(
    tmp_path, monkeypatch, clean_env
):
    # Even with a scaffolded unit present, --resolve-only adds no provenance /
    # progress / docs: the on-disk tree is byte-for-byte unchanged.
    monkeypatch.chdir(tmp_path)
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=tmp_path, intent=Intent.reference, audience="devs")
    before = _snapshot(tmp_path)

    result = runner.invoke(app, ["draft", "u", "--resolve-only", "--provider", "mock"])
    assert result.exit_code == 0, result.output
    assert _snapshot(tmp_path) == before
    unit_dir = tmp_path / ".dogen" / "units" / "u"
    assert not (unit_dir / "provenance.yaml").exists()
    assert not (unit_dir / "progress.yaml").exists()
    assert not (tmp_path / "docs").exists()


def test_resolve_only_json_prints_provider_null_side_effect_fields(
    tmp_path, monkeypatch, clean_env
):
    # The --json object reports the resolved provider with null draft_path /
    # progress / reason (nothing ran).
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app, ["draft", "u", "--resolve-only", "--json", "--provider", "mock"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {
        "unit": "u",
        "provider": "mock",
        "draft_path": None,
        "progress": None,
        "reason": None,
    }
    assert not (tmp_path / ".dogen").exists()


def test_resolve_only_reads_dogen_provider_env(tmp_path, monkeypatch, clean_env):
    # Precedence rung 2: with no --provider flag, DOGEN_PROVIDER=mock resolves mock.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOGEN_PROVIDER", "mock")

    result = runner.invoke(app, ["draft", "u", "--resolve-only", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["provider"] == "mock"


def test_explicit_provider_overrides_dogen_provider_env(
    tmp_path, monkeypatch, clean_env
):
    # Precedence rung 1: an explicit --provider host-harness overrides
    # DOGEN_PROVIDER=mock (flag > env, D-06).
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOGEN_PROVIDER", "mock")

    result = runner.invoke(
        app, ["draft", "u", "--resolve-only", "--json", "--provider", "host-harness"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["provider"] == "host-harness"


def test_resolve_only_auto_default_resolves_offline_to_passenger(
    tmp_path, monkeypatch, clean_env
):
    # Precedence rung 3: with no flag and no env, auto resolves OFFLINE. With the
    # SDK-disable escape hatch set, the probe yields the host-harness passenger
    # (never mock) — no network at resolution time (D-05/D-06).
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOGEN_DISABLE_COPILOT", "1")

    result = runner.invoke(app, ["draft", "u", "--resolve-only", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["provider"] == "host-harness"
