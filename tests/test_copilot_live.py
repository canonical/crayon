"""Token-gated live driver test — scaffolds the D-15 "≥1 recorded live run".

Unlike ``tests/test_copilot_e2e_offline.py`` (the CI keystone, fake-SDK
transport), this exercises the *real* ``CopilotDraftingProvider`` against the
live Copilot runtime: no stub, an actual model call. It therefore MUST **skip,
never fail**, whenever the Copilot auth token is absent, so the offline suite
stays green in CI (D-15). The recorded live run itself is a Manual-Only
verification (03-VALIDATION.md): fetch the runtime via
``python -m copilot download-runtime``, export the token, and run this file.

Skip gate (Open Question 1, confirmed against the installed
``github-copilot-sdk==1.0.2``): the SDK forwards its auth token to the CLI
runtime via ``--auth-token-env COPILOT_SDK_AUTH_TOKEN`` and populates
``COPILOT_SDK_AUTH_TOKEN`` from the ``github_token`` option
(``copilot/client.py``). That env var is the SDK's own auth-token name, so its
presence is the cheap, offline availability signal we gate on. Reading
``os.environ`` at collection triggers **no** network call or runtime fetch; the
runtime is only ever spawned inside the (un-skipped) test body's draft.
"""

from __future__ import annotations

import os
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

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The SDK's own auth-token env var (confirmed against github-copilot-sdk==1.0.2,
# copilot/client.py: ``--auth-token-env COPILOT_SDK_AUTH_TOKEN``). Its presence is
# the offline availability signal; absence skips (never fails) so CI stays green.
_LIVE_TOKEN_ENV = "COPILOT_SDK_AUTH_TOKEN"

_UNIT_ID = "dogen-live-reference"

# The driver's authoritative provenance identity (D-14/D-12), asserted on the
# recorded generation when the test runs live.
_DRIVER_SDK = "github-copilot-sdk==1.0.2"
_DRIVER_MODE = "driver"


def _stamp() -> str:
    return "2026-01-01T00:00:00Z"


def _identity() -> tuple[str, str]:
    return ("Ada Lovelace", "ada@example.com")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get(_LIVE_TOKEN_ENV),
    reason="live Copilot token/runtime not available "
    f"({_LIVE_TOKEN_ENV} unset); recorded live run is Manual-Only (03-VALIDATION.md)",
)
async def test_live_driver_draft_records_authoritative_provenance(
    tmp_path: Path,
) -> None:
    # Real integration: no stub. Only reached when a token is present, so the
    # runtime spawn/network never happens in the token-less CI run above.
    store = FilesystemPlanningStore()
    declare(
        DeclareRequest(
            unit_id=_UNIT_ID,
            root=tmp_path,
            store=store,
            intent=Intent.reference,
            audience="operators",
        )
    )
    steer(
        SignoffRequest(
            unit_id=_UNIT_ID, root=tmp_path, store=store, identity=_identity, now=_stamp
        )
    )

    # working_directory = the repo root so the live read-only agent can ground the
    # draft in real files; the draft still lands under tmp_path/docs via the store.
    outcome = await draft(
        DraftRequest(
            unit_id=_UNIT_ID,
            root=tmp_path,
            provider=CopilotDraftingProvider(working_directory=str(_REPO_ROOT)),
            store=store,
            provider_name="copilot",
            now=_stamp,
        )
    )

    # A non-empty drafted docs/ file (the real model produced MyST).
    draft_path = outcome.path
    assert draft_path.exists()
    assert draft_path.read_text(encoding="utf-8").strip()

    # The recorded generation carries the driver's authoritative identity.
    provenance = store.read_provenance(_UNIT_ID, root=tmp_path)
    assert len(provenance.generations) == 1
    generation = provenance.generations[0]
    assert generation.mode == _DRIVER_MODE
    assert generation.sdk == _DRIVER_SDK
    assert generation.provider == "copilot"

    # PROV-04: the drafted state derives from the recorded generation.
    assert derive_progress(provenance) is ProgressState.drafted
