"""Model identity: persist + resolve + show/set + the D-03 vouch-origin table.

The shared Wave-0 scaffold for Phase 8's model-identity slice (MODEL-01/MODEL-02,
design §D4). It mirrors the project's per-module fixture convention
(``conftest.py`` holds only the Copilot SDK stubs) copied from
``tests/test_ownership_lease_e2e.py`` / ``tests/test_loop_mock_e2e.py``: a
deterministic ``_Clock``, a real tmp-``repo`` git-seam fixture, a
``FilesystemPlanningStore()``, a mock provider, and ``_declare`` / ``_signoff`` /
``_draft`` helpers built onto one unit carrying ≥1 recorded generation. Plans
02/03 extend this file rather than re-declaring the scaffold.

Coverage in this plan:

* ``-k set`` / ``-k show`` — the ``DogenConfig.model`` / ``model_origin`` config
  round-trip (write → read-back preserves both; an old config with no ``model``
  key loads as honest-empty; no schema bump) and the ``dogen model show|set``
  CLI JSON contract.
* ``-k resolve`` / ``-k unrecorded`` — the pure ``resolve_model_name`` precedence
  (flag > env > config, honest-empty when all absent) + ``model_resolution_source``
  show-label.
* ``-k origin`` — the D-03 ``model_generation_origin`` vouch table.
* ``-k validate`` — ``validate_model_name`` refuses empty / multi-line /
  control-char names before they reach a trailer or YAML scalar (V5).
"""

import json
import subprocess

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
from dogen.cli.main import app
from dogen.core.models import DogenConfig, Intent
from dogen.core.orchestrator import draft
from dogen.core.orchestrator import signoff as steer

runner = CliRunner()


def _payload(result) -> dict:
    """Parse the single JSON object line from a CLI result.

    ``configure_observability`` routes the console span to stderr, but
    ``CliRunner`` folds stderr back into ``result.output``; scan for the one JSON
    line so the assertion survives that interleaving.
    """
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON object in output: {result.output!r}")


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock (no real time)."""

    def __init__(self):
        self._n = 0

    def __call__(self):
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with a configured local identity, used as the working dir.

    ``read_git_identity`` reads ``git config --get`` in the cwd, so the local
    user.name/email set here resolve deterministically with no network.
    ``DOGEN_MODEL`` / ``DOGEN_PROVIDER`` are cleared so an ambient env pin never
    overrides the values under test.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ada@example.com"],
        check=True,
    )
    monkeypatch.delenv("DOGEN_MODEL", raising=False)
    monkeypatch.delenv("DOGEN_PROVIDER", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _declare(store, root, *, unit, sphinx_target="guide.md", repo=None):
    """Declare ``unit`` onto ``sphinx_target`` through the promoted core use-case."""
    from dogen.core.orchestrator import declare

    declare(
        compose.build_declare_request(
            unit,
            root=root,
            store=store,
            intent=Intent.reference,
            audience="devs",
            sphinx_target=sphinx_target,
            repo=repo,
        )
    )


def _signoff(store, root, clock, *, unit, repo=None):
    """Record the HITL steering sign-off for ``unit`` (the draft-gate precondition)."""
    return steer(
        compose.build_signoff_request(unit, root=root, store=store, now=clock, repo=repo)
    )


async def _draft(store, root, clock, *, unit, provider="mock", repo=None):
    """Drive one mock draft of ``unit``, recording ≥1 generation; returns the outcome."""
    return await draft(
        compose.build_draft_request(
            unit,
            root=root,
            store=store,
            now=clock,
            provider=provider,
            repo=repo,
        )
    )


@pytest.fixture
def unit_with_generation(repo):
    """A repo carrying one declared+steered+drafted unit (≥1 recorded generation).

    The shared Wave-0 fixture Plans 02/03 reuse: returns ``(store, root, clock,
    unit_id)`` after a mock draft has recorded a generation onto ``u``.
    """
    import asyncio

    store = FilesystemPlanningStore()
    clock = _Clock()
    unit = "u"
    _declare(store, repo, unit=unit)
    _signoff(store, repo, clock, unit=unit)
    asyncio.run(_draft(store, repo, clock, unit=unit))
    return store, repo, clock, unit


# --------------------------------------------------------------------------- #
# Task 1 — DogenConfig.model / model_origin config round-trip (-k set)
# --------------------------------------------------------------------------- #


def test_fresh_config_has_empty_model_and_origin():
    config = DogenConfig()
    assert config.model == ""
    assert config.model_origin == ""


def test_config_roundtrips_model_and_origin_from_dict():
    config = DogenConfig(
        **{"provider": "mock", "model": "gpt-x", "model_origin": "ta"}
    )
    assert config.model == "gpt-x"
    assert config.model_origin == "ta"


def test_config_set_write_then_read_preserves_model_and_origin(repo):
    # Named for `-k set`: the write/read-back round-trip through the FS store.
    store = FilesystemPlanningStore()
    config = DogenConfig(provider="mock", model="gpt-x", model_origin="self")
    store.write_config(config, root=repo)
    read_back = store.read_config(root=repo)
    assert read_back.model == "gpt-x"
    assert read_back.model_origin == "self"


def test_old_config_without_model_key_loads_as_empty():
    # An old config dict with NO model key loads (honest-empty) — no migration.
    config = DogenConfig(**{"schema_version": 2, "provider": "host-harness"})
    assert config.model == ""
    assert config.model_origin == ""
