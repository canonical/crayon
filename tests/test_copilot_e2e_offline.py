"""Offline driver e2e — the DRAFT-04 CI keystone (D-15, no token, no network).

This drives the *real*
:class:`~dogen.adapters.copilot.provider.CopilotDraftingProvider` through the
unchanged orchestrator :func:`~dogen.core.orchestrator.draft` spine against the
fake-SDK transport injected by the shared ``install_stub_client`` fixture (plan
03-02). The stub *is* the transport, so no Copilot token, runtime, or network is
touched — the whole path runs green in CI.

The proof, fully offline:

* ``test_offline_driver_e2e_records_authoritative_provenance`` — the recorded
  ``generations[0]`` carries the driver's authoritative identity
  (``mode="driver"``, ``sdk="github-copilot-sdk==1.0.2"``, ``provider="copilot"``)
  and the WR-03 provenance-before-output ordering held (a generation row and a
  ``drafted`` progress transition were persisted alongside the written draft).

The stub scripts a canned ``assistant.message`` whose ``content`` is valid MyST
(``conftest._StubAssistantData``); the orchestrator writes it to the unit's
Sphinx target under the unit's ``docs/`` output path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dogen.adapters.copilot.provider import CopilotDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.core.models import Intent, ProgressState, derive_progress
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

# The offline reference unit; the store sets sphinx_target = "<unit_id>.md", so the
# draft lands at the unit's docs/dogen-reference.md output path.
_UNIT_ID = "dogen-reference"

# The canned MyST the fake-SDK stub returns (conftest._StubAssistantData.content).
# Asserted verbatim so a stub-content drift is caught here.
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

    # (c) provenance-before-output ordering held (WR-03): the generation row was
    # persisted for this run and IS the drafted state — derived from the record
    # (PROV-04), never a separately-persisted progress transition.
    assert generation.action == "draft"
    assert generation.run_id  # correlated to the draft span
    assert derive_progress(provenance) is ProgressState.drafted
