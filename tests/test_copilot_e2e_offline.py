"""Offline driver e2e — the DRAFT-04 CI keystone (D-15, no token, no network).

This drives the *real*
:class:`~dogen.adapters.copilot.provider.CopilotDraftingProvider` through the
unchanged orchestrator :func:`~dogen.core.orchestrator.draft` spine against the
fake-SDK transport injected by the shared ``install_stub_client`` fixture (plan
03-02). The stub *is* the transport, so no Copilot token, runtime, or network is
touched — the whole path runs green in CI.

Two proofs, both fully offline:

* ``test_offline_driver_e2e_records_authoritative_provenance`` — the recorded
  ``generations[0]`` carries the driver's authoritative identity
  (``mode="driver"``, ``sdk="github-copilot-sdk==1.0.2"``, ``provider="copilot"``)
  and the WR-03 provenance-before-output ordering held (a generation row and a
  ``drafted`` progress transition were persisted alongside the written draft).
* ``test_offline_driver_draft_compiles_under_sphinx_w`` — the driver's canned
  MyST, written to ``docs/`` through the store, compiles warning-free under the
  same ``sphinx-build -W`` publishability gate ``tests/test_docs_build.py`` uses
  (DRAFT-04 publishability, D-15 / Assumption A4).

The stub scripts a canned ``assistant.message`` whose ``content`` is valid MyST
(``conftest._StubAssistantData``); the orchestrator writes it to the unit's
Sphinx target, which the committed ``docs/index.md`` toctree names, so ``-W``
compiles the loop's real output rather than an empty tree (Pitfall 3).
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from dogen.adapters.copilot.provider import CopilotDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.core.models import Intent, ProgressState
from dogen.core.orchestrator import (
    DeclareRequest,
    DraftRequest,
    SignoffRequest,
    declare,
    draft,
)
from dogen.core.orchestrator import (
    signoff as steer,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _REPO_ROOT / "docs"

# The reference unit the committed docs/index.md toctree names; the scaffold sets
# sphinx_target = "<unit_id>.md", so the draft lands at docs/dogen-reference.md
# (the toctree entry), matching tests/test_docs_build.py.
_UNIT_ID = "dogen-reference"

# The canned MyST the fake-SDK stub returns (conftest._StubAssistantData.content).
# Asserted verbatim so a stub-content drift is caught here, and compiled under -W.
_CANNED_MYST = "# Drafted\n\nbody"

# The driver's authoritative provenance identity, stamped once at the mapping seam
# (adapters/copilot/mapping.py, D-14/D-12). Duplicated here as the assertion target.
_DRIVER_SDK = "github-copilot-sdk==1.0.2"
_DRIVER_MODE = "driver"


def _stamp() -> str:
    return "2026-01-01T00:00:00Z"


def _identity() -> tuple[str, str]:
    # A stub Identity port so steering needs no git repo (offline).
    return ("Ada Lovelace", "ada@example.com")


def _declare_and_steer(root: Path, store: FilesystemPlanningStore) -> None:
    """Declare the reference unit and record its HITL steering act (offline)."""
    declare(
        DeclareRequest(
            unit_id=_UNIT_ID,
            root=root,
            store=store,
            intent=Intent.reference,
            audience="operators",
        )
    )
    steer(
        SignoffRequest(
            unit_id=_UNIT_ID, root=root, store=store, identity=_identity, now=_stamp
        )
    )


def _draft_request(root: Path, store: FilesystemPlanningStore) -> DraftRequest:
    """Build the DraftRequest driving the real Copilot provider through the loop."""
    return DraftRequest(
        unit_id=_UNIT_ID,
        root=root,
        provider=CopilotDraftingProvider(),
        store=store,
        provider_name="copilot",
        now=_stamp,
    )


@pytest.mark.asyncio
async def test_offline_driver_e2e_records_authoritative_provenance(
    tmp_path: Path, install_stub_client
) -> None:
    # The fake-SDK stub is the transport: happy-path canned assistant.message,
    # no network, no token (conftest.install_stub_client patches the SDK boundary).
    install_stub_client()

    store = FilesystemPlanningStore()
    _declare_and_steer(tmp_path, store)

    draft_path = (await draft(_draft_request(tmp_path, store))).path

    # (a) the draft landed at the unit's Sphinx target under docs/ with the
    # driver's canned MyST verbatim (store.write_draft path).
    assert draft_path == (tmp_path / "docs" / f"{_UNIT_ID}.md")
    assert draft_path.exists()
    assert draft_path.read_text(encoding="utf-8") == _CANNED_MYST

    # (b) the recorded generation carries the driver's authoritative identity.
    provenance = store.read_provenance(_UNIT_ID, root=tmp_path)
    assert provenance.signoff is not None  # HITL act provably precedes the draft
    assert len(provenance.generations) == 1
    generation = provenance.generations[0]
    assert generation.mode == _DRIVER_MODE
    assert generation.sdk == _DRIVER_SDK
    assert generation.provider == "copilot"

    # (c) provenance-before-output ordering held (WR-03): the generation row and
    # the auto-advanced progress transition were both persisted for this run.
    assert generation.action == "draft"
    assert generation.run_id  # correlated to the draft span
    progress = store.read_progress(_UNIT_ID, root=tmp_path)
    assert progress.state is ProgressState.drafted


@pytest.mark.skipif(
    shutil.which("sphinx-build") is None,
    reason="sphinx-build not installed (docs extra); CI runs it with --extra docs",
)
def test_offline_driver_draft_compiles_under_sphinx_w(
    tmp_path: Path, install_stub_client
) -> None:
    # Assemble a docs tree = the committed conf.py + index.md + the driver's
    # drafted page, then run a real -W build over it. The fake-SDK stub is the
    # only transport — no Copilot token, no network (mirrors test_docs_build.py).
    install_stub_client()

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    shutil.copy(_DOCS / "conf.py", docs_dir / "conf.py")
    shutil.copy(_DOCS / "index.md", docs_dir / "index.md")

    store = FilesystemPlanningStore()
    _declare_and_steer(tmp_path, store)
    asyncio.run(draft(_draft_request(tmp_path, store)))

    drafted = docs_dir / f"{_UNIT_ID}.md"
    # The driver's MyST must be the page the toctree references, so -W compiles
    # the loop's real output rather than an empty tree (Pitfall 3).
    assert drafted.exists()

    out = tmp_path / "_out"
    result = subprocess.run(  # noqa: S603
        ["sphinx-build", "-W", "-b", "html", str(docs_dir), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
