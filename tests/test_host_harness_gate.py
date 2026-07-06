"""Passenger record-time gate: unsteered draft refuses with zero side effects.

Covers DRAFT-05 gate (Plan 04, Task 2) and locks tampering threat T-03-02
(high, mitigate). The shared orchestrator gate (D-04) treats the passenger
identically to the driver: an unsteered draft raises
:class:`SignoffRequiredError` *before* any side effect, so no provenance
generation, progress transition, or ``docs/`` file is written. The host's
handoff text is read-only input — dogen holds it in memory and never writes or
deletes the on-disk handoff file, which stays byte-for-byte unchanged.

Fully offline: no token, no network (D-17).
"""

from pathlib import Path

import pytest

from dogen.adapters.host_harness import HostHarnessDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.core.models import (
    Intent,
    Progress,
    ProgressState,
    Provenance,
)
from dogen.core.orchestrator import DraftRequest, SignoffRequiredError, draft

_HANDOFF_BYTES = b"# Draft from the host\n\nThis handoff file must never be touched.\n"


class _Clock:
    """A deterministic ISO-8601 clock (never expected to be called here)."""

    def __call__(self) -> str:
        return "2026-01-01T00:00:00Z"


def _seed_unsteered_unit(root: Path) -> FilesystemPlanningStore:
    """Seed a unit with NO steering event (provenance.steering is None)."""
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=Intent.reference, audience="devs")
    store.write_provenance(Provenance(unit_id="u", signoff=None), root=root)
    store.write_progress(Progress(unit_id="u", state=ProgressState.pending), root=root)
    return store


@pytest.mark.asyncio
async def test_unsteered_passenger_refuses_with_zero_side_effects(
    tmp_path: Path,
) -> None:
    store = _seed_unsteered_unit(tmp_path)
    # A handoff file the host produced, sitting on disk. dogen reads its text
    # into the provider in memory; the file itself is never dogen's to touch.
    handoff = tmp_path / "handoff.md"
    handoff.write_bytes(_HANDOFF_BYTES)
    provider = HostHarnessDraftingProvider(
        draft_text=handoff.read_text(encoding="utf-8")
    )
    request = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=provider,
        store=store,
        provider_name="host-harness",
        now=_Clock(),
    )

    with pytest.raises(SignoffRequiredError):
        await draft(request)

    # Zero side effects (D-04): no generation recorded, progress unmoved, no
    # draft written under docs/.
    assert store.read_provenance("u", root=tmp_path).generations == []
    assert store.read_progress("u", root=tmp_path).state is ProgressState.pending
    assert not (tmp_path / "docs" / "u.md").exists()

    # T-03-02: the read-only handoff file is left byte-for-byte untouched.
    assert handoff.read_bytes() == _HANDOFF_BYTES
