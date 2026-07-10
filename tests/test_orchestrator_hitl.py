"""Orchestrator behaviour: HITL gate, run_id correlation, progress lifecycle.

Covers Task 2. The use-case is exercised against a *real*
:class:`FilesystemPlanningStore` over a tmp dir and the deterministic
:class:`MockDraftingProvider` (mock only at the true provider boundary,
coding-guide §4). OBS-03 correlation is checked with a test-only in-memory OTel
SDK exporter; the core itself stays API-only.
"""

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
    Effort,
    Intent,
    ProgressState,
    Provenance,
    ReviewerEdit,
    Signoff,
    SourceRef,
    Unit,
    derive_progress,
)
from dogen.core.orchestrator import DraftRequest, SignoffRequiredError, draft


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
        Signoff(
            author="Ada",
            at="2026-01-01T00:00:00Z",
            intent=Intent.reference,
            audience="devs",
        )
        if with_steering
        else None
    )
    store.write_provenance(Provenance(unit_id="u", signoff=steering), root=root)
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
    with pytest.raises(SignoffRequiredError):
        await draft(_request(tmp_path, store))
    assert not (tmp_path / "docs" / "u.md").exists()
    assert store.read_provenance("u", root=tmp_path).generations == []
    assert (
        derive_progress(store.read_provenance("u", root=tmp_path))
        is ProgressState.pending
    )


@pytest.mark.asyncio
async def test_draft_writes_correlated_generation(
    tmp_path: Path, in_memory_spans: InMemorySpanExporter
) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    draft_path = (await draft(_request(tmp_path, store))).path
    assert draft_path.exists()
    provenance = store.read_provenance("u", root=tmp_path)
    assert len(provenance.generations) == 1
    run_id = provenance.generations[0].run_id
    finished = in_memory_spans.get_finished_spans()
    assert len(finished) == 1
    assert format(finished[0].context.trace_id, "032x") == run_id


@pytest.mark.asyncio
async def test_generation_stamps_provider_and_mode(tmp_path: Path) -> None:
    # PLAN-02 / OQ-1 (on-record half): the written generation records the
    # provider name (from the request) and a non-empty run mode, so provenance
    # carries provider/mode on disk — not merely as an OTel span attribute.
    store = _seed_unit(tmp_path, with_steering=True)
    await draft(_request(tmp_path, store))
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.provider == "mock"
    # D-12: the mock is a driver double, so its recorded run mode is now the
    # provider-reported "driver" (was the retired "local" module constant).
    assert generation.mode == "driver"
    assert generation.mode  # a non-empty run mode is recorded
    # D-14: SDK-free provider stamps an empty sdk id, not the copilot SDK string.
    assert generation.sdk == ""


@pytest.mark.asyncio
async def test_draft_advances_progress_to_drafted(tmp_path: Path) -> None:
    # PROV-04: the recorded generation IS the drafted state — derived from the
    # record, never a stamped ladder in a second stored artefact.
    store = _seed_unit(tmp_path, with_steering=True)
    await draft(_request(tmp_path, store))
    provenance = store.read_provenance("u", root=tmp_path)
    assert derive_progress(provenance) is ProgressState.drafted


@pytest.mark.asyncio
async def test_redraft_does_not_move_progress_backward(tmp_path: Path) -> None:
    # Re-drafting an already-drafted unit stays drafted — the count-based rule is
    # monotonic by construction (PROV-04), so there is no backward walk to guard.
    store = _seed_unit(tmp_path, with_steering=True)
    await draft(_request(tmp_path, store))
    assert (
        derive_progress(store.read_provenance("u", root=tmp_path))
        is ProgressState.drafted
    )
    await draft(_request(tmp_path, store))
    assert (
        derive_progress(store.read_provenance("u", root=tmp_path))
        is ProgressState.drafted
    )


@pytest.mark.asyncio
async def test_redraft_of_reviewed_resets_to_drafted(tmp_path: Path) -> None:
    # Re-drafting a *reviewed* unit supersedes the now-stale review and derives
    # back to ``drafted``: the fresh generation snapshots the current
    # reviewer-edit count, so the count is no longer strictly greater (PROV-04).
    store = _seed_unit(tmp_path, with_steering=True)
    await draft(_request(tmp_path, store))
    # Simulate a completed review by appending a reviewer edit to the record.
    prov = store.read_provenance("u", root=tmp_path)
    prov.reviewer_edits.append(
        ReviewerEdit(at="2026-01-01T00:01:00Z", reviewer="Ada", summary="reviewed")
    )
    store.write_provenance(prov, root=tmp_path)
    assert (
        derive_progress(store.read_provenance("u", root=tmp_path))
        is ProgressState.reviewed
    )
    # Re-draft the reviewed unit — it falls back to drafted.
    await draft(_request(tmp_path, store))
    assert (
        derive_progress(store.read_provenance("u", root=tmp_path))
        is ProgressState.drafted
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
    assert [o.path for o in generation.context_origins] == ["docs/actually_read.md"]
    assert generation.tools_used == ["builtin:view"]


@pytest.mark.asyncio
async def test_generation_records_provider_reported_effort(tmp_path: Path) -> None:
    # IN-03: when the provider reports the effort it actually ran at, the
    # recorded generation uses that value, not the requested DraftRequest.effort.
    store = _seed_unit(tmp_path, with_steering=True)

    class _EffortReportingProvider:
        async def draft_unit(self, **_kwargs: object) -> DraftResult:
            return DraftResult(
                text="# drafted",
                model="m",
                model_version="v",
                output_tokens=1,
                run_id="",
                effort_used=Effort.xhigh,
            )

    request = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=_EffortReportingProvider(),
        store=store,
        provider_name="reporting",
        now=_Clock(),
        effort=Effort.low,  # requested low, but provider ran xhigh
    )
    await draft(request)
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.effort is Effort.xhigh


@pytest.mark.asyncio
async def test_generation_falls_back_to_requested_effort(tmp_path: Path) -> None:
    # IN-03: when the provider reports no effort (mock), the requested effort
    # stands so the audit entry is never left blank.
    store = _seed_unit(tmp_path, with_steering=True)
    request = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=MockDraftingProvider(),
        store=store,
        provider_name="mock",
        now=_Clock(),
        effort=Effort.high,
    )
    await draft(request)
    generation = store.read_provenance("u", root=tmp_path).generations[0]
    assert generation.effort is Effort.high


@pytest.mark.asyncio
async def test_provenance_is_durable_before_draft_write(tmp_path: Path) -> None:
    # WR-03: the audit record (provenance) must be written BEFORE the draft file,
    # so a failure during the draft write can never leave a drafted output with no
    # recorded generation. Here write_draft raises; the generation must already be
    # on disk (drafted state derives from it), and no draft .md must exist.
    store = _seed_unit(tmp_path, with_steering=True)

    class _FailingDraftStore(FilesystemPlanningStore):
        # A real (stateless) store whose draft write fails, to prove the audit
        # row is durable before the draft file is written. Subclassing the real
        # store keeps this a genuine PlanningStore, so the type checker needs no
        # suppression; every other call still hits the real implementation
        # against the same tmp_path.
        def write_draft(self, unit: Unit, text: str, *, root: Path) -> Path:
            raise OSError("disk full")

    failing = _FailingDraftStore()
    request = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=MockDraftingProvider(),
        store=failing,
        provider_name="mock",
        now=_Clock(),
    )
    with pytest.raises(OSError, match="disk full"):
        await draft(request)
    # Audit row is durable even though the draft write failed.
    provenance = store.read_provenance("u", root=tmp_path)
    assert len(provenance.generations) == 1
    assert derive_progress(provenance) is ProgressState.drafted
    # The draft .md was never written (no orphan output without provenance).
    assert not (tmp_path / "docs" / "u.md").exists()


@pytest.mark.asyncio
async def test_draft_reads_prior_steering_act(tmp_path: Path) -> None:
    # Drafting must follow steering written by a *prior* act, not this call.
    store = _seed_unit(tmp_path, with_steering=True)
    before = store.read_provenance("u", root=tmp_path)
    assert before.signoff is not None
    assert before.generations == []
    await draft(_request(tmp_path, store))
    after = store.read_provenance("u", root=tmp_path)
    assert after.signoff is not None
    assert after.signoff.at < after.generations[0].at


# --- Phase 5: shared seal helper + real tooling_version (PROV-01/PROV-06) ------


def test_same_file_digests_is_order_agnostic() -> None:
    from dogen.core.models import FileDigest  # noqa: PLC0415
    from dogen.core.orchestrator import same_file_digests  # noqa: PLC0415

    a = [
        FileDigest(path="docs/a.md", sha256="1"),
        FileDigest(path="docs/b.md", sha256="2"),
    ]
    reordered = [
        FileDigest(path="docs/b.md", sha256="2"),
        FileDigest(path="docs/a.md", sha256="1"),
    ]
    changed = [
        FileDigest(path="docs/a.md", sha256="1"),
        FileDigest(path="docs/b.md", sha256="CHANGED"),
    ]
    assert same_file_digests(a, reordered) is True
    assert same_file_digests(a, changed) is False


def test_tooling_version_reads_installed_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orchestrator._metadata, "version", lambda name: "9.9.9")
    assert orchestrator.tooling_version() == "9.9.9"


def test_tooling_version_falls_back_on_missing_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.metadata  # noqa: PLC0415

    def _raise(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(orchestrator._metadata, "version", _raise)
    fallback = orchestrator.tooling_version()
    # Honest, non-semver sentinel — not a fabricated version string.
    assert "+" in fallback
