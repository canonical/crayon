# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

"""Orchestrator behaviour: HITL gate, run_id correlation, progress lifecycle.

Covers Task 2. The use-case is exercised against a *real*
:class:`FilesystemPlanningStore` over a tmp dir and the deterministic
:class:`MockDraftingProvider` (mock only at the true provider boundary,
coding-guide §4). OBS-03 correlation is checked with a test-only in-memory OTel
SDK exporter; the core itself stays API-only.
"""

import ast
from pathlib import Path

import pytest
import yaml
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from dogen.adapters.mock_provider import MockDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore, split_front_matter
from dogen.core import orchestrator
from dogen.core.models import (
    DraftResult,
    Intent,
    Progress,
    ProgressEntry,
    ProgressState,
    Provenance,
    SourceRef,
    Steering,
    Unit,
)
from dogen.core.orchestrator import DraftRequest, SteeringRequiredError, draft


@pytest.fixture
def in_memory_spans() -> InMemorySpanExporter:
    """Install a test-only in-memory OTel SDK exporter and return it."""
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # noqa: SLF001
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


def _seed_unit(root: Path, *, with_steering: bool) -> FilesystemPlanningStore:
    """Write a unit + provenance + progress to a tmp root for the use-case.

    Parameters
    ----------
    root : Path
        The tmp repo root.
    with_steering : bool
        Whether to seed a recorded steering event.
    """
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=Intent.reference, audience="devs")
    unit_md = root / ".dogen" / "units" / "u" / "unit.md"
    front, body = store_split(unit_md)
    unit = Unit(**front)
    unit.sources = [SourceRef(path="README.md")]
    unit.title = "About dogen"
    _rewrite_unit_md(unit_md, unit, body)
    steering = (
        Steering(
            author="Ada",
            at="2026-01-01T00:00:00Z",
            intent=Intent.reference,
            audience="devs",
        )
        if with_steering
        else None
    )
    store.write_provenance(Provenance(unit_id="u", steering=steering), root=root)
    store.write_progress(Progress(unit_id="u", state=ProgressState.pending), root=root)
    return store


def store_split(path: Path) -> tuple[dict, str]:
    """Split a unit.md into front-matter and body via the store's splitter."""
    return split_front_matter(path.read_text(encoding="utf-8"))


def _rewrite_unit_md(path: Path, unit: Unit, body: str) -> None:
    """Persist an edited Unit back to unit.md front-matter for the test."""
    front = yaml.safe_dump(unit.model_dump(mode="json"), sort_keys=False).rstrip("\n")
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")


def _request(root: Path, store: FilesystemPlanningStore) -> DraftRequest:
    """Build a DraftRequest wired to the mock provider and a deterministic clock."""
    return DraftRequest(
        unit_id="u",
        root=root,
        provider=MockDraftingProvider(),
        store=store,
        provider_name="mock",
        now=_Clock(),
    )


@pytest.mark.asyncio
async def test_draft_refuses_without_steering(tmp_path: Path) -> None:
    store = _seed_unit(tmp_path, with_steering=False)
    with pytest.raises(SteeringRequiredError):
        await draft(_request(tmp_path, store))
    assert not (tmp_path / "docs" / "u.md").exists()
    assert store.read_provenance("u", root=tmp_path).generations == []
    assert store.read_progress("u", root=tmp_path).state is ProgressState.pending


@pytest.mark.asyncio
async def test_draft_writes_correlated_generation(
    tmp_path: Path, in_memory_spans: InMemorySpanExporter
) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    draft_path = await draft(_request(tmp_path, store))
    assert draft_path.exists()
    provenance = store.read_provenance("u", root=tmp_path)
    assert len(provenance.generations) == 1
    run_id = provenance.generations[0].run_id
    finished = in_memory_spans.get_finished_spans()
    assert len(finished) == 1
    assert format(finished[0].context.trace_id, "032x") == run_id


@pytest.mark.asyncio
async def test_draft_advances_progress_to_drafted(tmp_path: Path) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    await draft(_request(tmp_path, store))
    progress = store.read_progress("u", root=tmp_path)
    assert progress.state is ProgressState.drafted
    states = [e.state for e in progress.history]
    assert ProgressState.sourced in states
    assert ProgressState.drafted in states
    assert ProgressState.committed not in states


@pytest.mark.asyncio
async def test_redraft_does_not_move_progress_backward(tmp_path: Path) -> None:
    # Re-drafting an already-drafted unit must not regress to sourced nor
    # append spurious history entries (WR-04: monotonic, idempotent advance).
    store = _seed_unit(tmp_path, with_steering=True)
    await draft(_request(tmp_path, store))
    first = store.read_progress("u", root=tmp_path)
    first_history = list(first.history)
    await draft(_request(tmp_path, store))
    second = store.read_progress("u", root=tmp_path)
    # State stays drafted and no extra transitions were stamped on re-draft.
    assert second.state is ProgressState.drafted
    assert [e.state for e in second.history] == [e.state for e in first_history]
    assert ProgressState.sourced not in [
        e.state for e in second.history[len(first_history) :]
    ]


@pytest.mark.asyncio
async def test_redraft_of_reviewed_resets_to_drafted(tmp_path: Path) -> None:
    # Re-drafting a *reviewed* unit supersedes the now-stale review and resets
    # the unit to ``drafted`` in one clean transition — never the backward walk
    # through ``sourced`` the first WR-04 fix left in place (verifier follow-up).
    store = _seed_unit(tmp_path, with_steering=True)
    await draft(_request(tmp_path, store))
    # Simulate a completed review by advancing progress to ``reviewed``.
    reviewed = store.read_progress("u", root=tmp_path)
    reviewed.state = ProgressState.reviewed
    reviewed.history.append(
        ProgressEntry(at="2026-01-01T00:01:00Z", state=ProgressState.reviewed)
    )
    store.write_progress(reviewed, root=tmp_path)
    before_states = [e.state for e in reviewed.history]
    # Re-draft the reviewed unit.
    await draft(_request(tmp_path, store))
    after = store.read_progress("u", root=tmp_path)
    after_states = [e.state for e in after.history]
    # The fresh draft lands the unit back at ``drafted``...
    assert after.state is ProgressState.drafted
    # ...recorded as exactly one new ``drafted`` transition (no backward
    # ``sourced`` re-stamp, so the audit history stays trustworthy).
    assert after_states == [*before_states, ProgressState.drafted]
    assert after_states.count(ProgressState.sourced) == 1


def test_orchestrator_never_writes_committed() -> None:
    source = Path(orchestrator.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "committed":
            value = node.value
            assert not (isinstance(value, ast.Name) and value.id == "ProgressState"), (
                "orchestrator must never reference ProgressState.committed (SKEL-03)"
            )


@pytest.mark.asyncio
async def test_generation_does_not_fabricate_context_origins(tmp_path: Path) -> None:
    # BL-01/D-37: the recorded generation must NOT copy the unit's human-pointed
    # sources into ``context_origins`` (agent-read). The mock observes nothing,
    # so both ``context_origins`` and ``tools_used`` must be honestly empty even
    # though the unit declares a source.
    store = _seed_unit(tmp_path, with_steering=True)
    unit = store.load_unit("u", root=tmp_path)
    assert unit.sources  # the seeded unit declares a human-pointed source
    await draft(_request(tmp_path, store))
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.context_origins == []
    assert generation.tools_used == []


@pytest.mark.asyncio
async def test_generation_records_provider_reported_context(tmp_path: Path) -> None:
    # BL-01: when a provider *does* report what it read/ran, the orchestrator
    # records those values verbatim (not ``unit.sources``).
    store = _seed_unit(tmp_path, with_steering=True)

    class _ReportingProvider:
        async def draft_unit(self, **_kwargs: object) -> DraftResult:
            return DraftResult(
                text="# drafted",
                model="m",
                model_version="v",
                output_tokens=1,
                run_id="",
                context_origins=["docs/actually_read.md"],
                tools_used=["builtin:view"],
            )

    request = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=_ReportingProvider(),
        store=store,
        provider_name="reporting",
        now=_Clock(),
    )
    await draft(request)
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.context_origins == ["docs/actually_read.md"]
    assert generation.tools_used == ["builtin:view"]


@pytest.mark.asyncio
async def test_draft_reads_prior_steering_act(tmp_path: Path) -> None:
    # Drafting must follow steering written by a *prior* act, not this call.
    store = _seed_unit(tmp_path, with_steering=True)
    before = store.read_provenance("u", root=tmp_path)
    assert before.steering is not None
    assert before.generations == []
    await draft(_request(tmp_path, store))
    after = store.read_provenance("u", root=tmp_path)
    assert after.steering is not None
    assert after.steering.at < after.generations[0].at
