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
    Intent,
    Progress,
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
