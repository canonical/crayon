"""Passenger e2e: a host-produced draft recorded through the shared spine.

Covers DRAFT-05 (Plan 04, Task 2). The :class:`HostHarnessDraftingProvider` is
driven through the *real* :func:`orchestrator.draft` use-case over a real
:class:`FilesystemPlanningStore` on a tmp dir — the only double is the provider
itself (the true provider boundary, coding-guide §4). Fully offline: no token,
no network, so this runs in CI (D-17).

The two truths locked here (T-03-03, high, mitigate):

* the delegated generation is honest-empty — ``provider="host-harness"``,
  ``mode="passenger"``, empty ``context_origins``/``tools_used``, ``sdk=""``,
  ``model``/``model_version`` ``""`` (unknown) unless asserted — and the host
  text lands byte-for-byte at ``docs/<sphinx_target>``;
* a host-asserted ``model``/``model_version`` is recorded verbatim.
"""

from pathlib import Path

import pytest
import yaml

from dogen.adapters.host_harness import HostHarnessDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore, split_front_matter
from dogen.core.models import (
    Intent,
    Progress,
    ProgressState,
    Provenance,
    Signoff,
    SourceRef,
    Unit,
)
from dogen.core.orchestrator import DraftRequest, draft

# A small, valid MyST page standing in for the draft the host agent produced.
_HOST_DRAFT = (
    "# Configuring dogen\n\n"
    "This page was drafted by the host agent and recorded by the passenger.\n\n"
    "```{note}\n"
    "dogen transcribed this text; it read no sources to produce it.\n"
    "```\n"
)


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


def _seed_steered_unit(root: Path) -> FilesystemPlanningStore:
    """Seed a steered unit (unit.md + provenance + progress) on a tmp root."""
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=Intent.reference, audience="devs")
    unit_md = root / ".dogen" / "units" / "u" / "unit.md"
    front, body = split_front_matter(unit_md.read_text(encoding="utf-8"))
    unit = Unit(**front)
    unit.sources = [SourceRef(path="README.md")]
    unit.title = "About dogen"
    front_yaml = yaml.safe_dump(unit.model_dump(mode="json"), sort_keys=False).rstrip(
        "\n"
    )
    unit_md.write_text(f"---\n{front_yaml}\n---\n{body}", encoding="utf-8")
    steering = Signoff(
        author="Ada",
        at="2026-01-01T00:00:00Z",
        intent=Intent.reference,
        audience="devs",
    )
    store.write_provenance(Provenance(unit_id="u", signoff=steering), root=root)
    store.write_progress(Progress(unit_id="u", state=ProgressState.pending), root=root)
    return store


def _passenger_request(
    root: Path,
    store: FilesystemPlanningStore,
    provider: HostHarnessDraftingProvider,
) -> DraftRequest:
    """Wire a DraftRequest to the passenger provider and a deterministic clock."""
    return DraftRequest(
        unit_id="u",
        root=root,
        provider=provider,
        store=store,
        provider_name="host-harness",
        now=_Clock(),
    )


@pytest.mark.asyncio
async def test_passenger_records_delegated_generation(tmp_path: Path) -> None:
    # The passenger reuses the shared spine: it records a delegated honest-empty
    # generation and writes the host text to docs/ byte-symmetric with a driver.
    store = _seed_steered_unit(tmp_path)
    provider = HostHarnessDraftingProvider(draft_text=_HOST_DRAFT)
    draft_path = (await draft(_passenger_request(tmp_path, store, provider))).path

    generation = store.read_provenance("u", root=tmp_path).generations[0]
    # T-03-03: the whole record is marked delegated and carries no fabricated
    # read-context or tool activity, and no SDK it never used.
    assert generation.provider == "host-harness"
    assert generation.mode == "passenger"
    assert generation.context_origins == []
    assert generation.tools_used == []
    assert generation.sdk == ""

    # The host text lands verbatim at the unit's Sphinx target under docs/.
    assert draft_path == (tmp_path / "docs" / "u.md")
    assert draft_path.read_text(encoding="utf-8") == _HOST_DRAFT


@pytest.mark.asyncio
async def test_passenger_ignores_sources(tmp_path: Path) -> None:
    # A passenger reads nothing: sources must not influence the recorded draft.
    # The unit declares a source, yet the output is exactly the host text.
    store = _seed_steered_unit(tmp_path)
    provider = HostHarnessDraftingProvider(draft_text=_HOST_DRAFT)
    draft_path = (await draft(_passenger_request(tmp_path, store, provider))).path
    assert draft_path.read_text(encoding="utf-8") == _HOST_DRAFT
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.context_origins == []


@pytest.mark.asyncio
async def test_passenger_records_host_asserted_model(tmp_path: Path) -> None:
    # host_asserted: an explicit host model/model_version is recorded verbatim
    # (not the "host-harness" sentinel).
    store = _seed_steered_unit(tmp_path)
    provider = HostHarnessDraftingProvider(
        draft_text=_HOST_DRAFT,
        model="claude-opus-4",
        model_version="opus-4-20260514",
    )
    await draft(_passenger_request(tmp_path, store, provider))
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.model == "claude-opus-4"
    assert generation.model_version == "opus-4-20260514"
    # Still a delegated passenger record despite the asserted identity.
    assert generation.mode == "passenger"
    assert generation.sdk == ""


@pytest.mark.asyncio
async def test_passenger_model_defaults_to_unknown(tmp_path: Path) -> None:
    # host_asserted (omitted): when the host asserts no model, both fields
    # record "" (unknown, D-13) — the provider name is never recorded as a
    # model (a validation leg surfaced literal "host-harness" as a falsehood).
    store = _seed_steered_unit(tmp_path)
    provider = HostHarnessDraftingProvider(draft_text=_HOST_DRAFT)
    await draft(_passenger_request(tmp_path, store, provider))
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.model == ""
    assert generation.model_version == ""
