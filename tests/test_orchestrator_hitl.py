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
from dogen.adapters.planning_fs import (
    FilesystemPlanningStore,
    TargetClaimedError,
    split_front_matter,
)
from dogen.core import orchestrator
from dogen.core.models import (
    DraftResult,
    Effort,
    Intent,
    ProgressState,
    Provenance,
    ReviewerEdit,
    ReviewVerdict,
    Signoff,
    SourceRef,
    Step,
    StepEvidence,
    StepMode,
    StepStatus,
    StepVerdict,
    Unit,
    _sha256_text,
    derive_progress,
    derive_step_status,
)
from dogen.core.orchestrator import (
    DraftRequest,
    EvidenceIncompleteError,
    EvidenceRequiredError,
    PlanStepsRequest,
    RecordStepRequest,
    ReviewRequest,
    SignoffRequiredError,
    draft,
    plan_steps,
    record_step,
    review,
)


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
    # Re-drafting a *reviewed* unit with GENUINELY NEW content supersedes the
    # now-stale review and derives back to ``drafted``: the fresh generation
    # snapshots the current reviewer-edit count, so the count is no longer
    # strictly greater (PROV-04). A byte-identical redraft would instead be a
    # true no-op (D-02/MODEL-03) that records nothing and correctly leaves the
    # reviewed state untouched — so this test uses a provider whose text differs
    # from the mock's first pass to exercise the real-redraft reset.
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

    class _DifferentDraft:
        async def draft_unit(self, **_kwargs: object) -> DraftResult:
            return DraftResult(
                text="# a genuinely reworked page\n",
                model="mock-model",
                model_version="mock-1",
                output_tokens=1,
                run_id="",
            )

    # Re-draft the reviewed unit with new content — it records a fresh generation
    # and falls back to drafted.
    redraft = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=_DifferentDraft(),
        store=store,
        provider_name="mock",
        now=_Clock(),
    )
    await draft(redraft)
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


# --- Phase 12 (Plan 02): evidence micro-gate + macro-gate --------------------


def _prov_path(root: Path) -> Path:
    """Return the seeded unit's provenance.yaml path."""
    return root / ".dogen" / "units" / "u" / "provenance.yaml"


def _plan_one_step(
    root: Path,
    store: FilesystemPlanningStore,
    *,
    step_id: str = "s1",
    text: str = "run the check",
) -> None:
    """Write a one-step plan onto the seeded unit via the plan_steps use-case."""
    plan_steps(
        PlanStepsRequest(
            unit_id="u",
            root=root,
            store=store,
            now=_Clock(),
            steps=[Step(id=step_id, text=text)],
        )
    )


def _resolved_evidence(text: str) -> StepEvidence:
    """Build a passing, hash-bound StepEvidence that resolves ``text``'s step."""
    return StepEvidence(
        mode=StepMode.agent,
        command="pytest",
        output_sha256="a" * 64,
        output_excerpt="ok",
        exit_code=0,
        verdict=StepVerdict.passed,
        step_text_sha256=_sha256_text(text),
        at="2026-01-01T00:00:00Z",
    )


def _accept_request(root: Path, store: FilesystemPlanningStore) -> ReviewRequest:
    """Build an ``accept`` ReviewRequest wired to a deterministic identity/clock."""
    return ReviewRequest(
        unit_id="u",
        root=root,
        store=store,
        identity=lambda: ("Ada", "ada@example.com"),
        now=_Clock(),
        note="ship it",
        verdict=ReviewVerdict.accept,
    )


# --- micro-gate: record_step refuses done-without-proof, zero side effects ----


def test_record_step_refuses_pass_without_output_hash(tmp_path: Path) -> None:
    # EVID-02/D-11: a pass verdict lacking a captured-output hash is refused with
    # zero side effects — the provenance file is byte-unchanged and the step keeps
    # no evidence.
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store)
    before = _prov_path(tmp_path).read_text(encoding="utf-8")
    with pytest.raises(EvidenceRequiredError):
        record_step(
            RecordStepRequest(
                unit_id="u",
                root=tmp_path,
                store=store,
                now=_Clock(),
                step_id="s1",
                verdict=StepVerdict.passed,
                command="pytest",
                output_sha256="",  # missing well-shaped proof
                exit_code=0,
            )
        )
    assert _prov_path(tmp_path).read_text(encoding="utf-8") == before
    assert store.read_provenance("u", root=tmp_path).steps[0].evidence is None


def test_record_step_refuses_skip_without_reason(tmp_path: Path) -> None:
    # EVID-04/D-06: a skipped verdict without a reason is refused, zero writes.
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store)
    before = _prov_path(tmp_path).read_text(encoding="utf-8")
    with pytest.raises(EvidenceRequiredError):
        record_step(
            RecordStepRequest(
                unit_id="u",
                root=tmp_path,
                store=store,
                now=_Clock(),
                step_id="s1",
                verdict=StepVerdict.skipped,
                reason="",  # a skip must carry a reason
            )
        )
    assert _prov_path(tmp_path).read_text(encoding="utf-8") == before
    assert store.read_provenance("u", root=tmp_path).steps[0].evidence is None


def test_record_step_persists_wellshaped_pass(tmp_path: Path) -> None:
    # A well-shaped pass binds the evidence to the step text and resolves it.
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store, text="run the check")
    status = record_step(
        RecordStepRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            now=_Clock(),
            step_id="s1",
            verdict=StepVerdict.passed,
            mode=StepMode.agent,
            command="pytest",
            output_sha256="b" * 64,
            output_excerpt="1 passed",
            exit_code=0,
        )
    )
    step = store.read_provenance("u", root=tmp_path).steps[0]
    assert step.evidence is not None
    assert step.evidence.verdict is StepVerdict.passed
    assert step.evidence.step_text_sha256 == _sha256_text("run the check")
    assert derive_step_status(step) is StepStatus.resolved
    assert status is StepStatus.resolved


def test_record_step_records_fail_without_resolving(tmp_path: Path) -> None:
    # D-07: fail is recorded (well-shaped) but never resolves the step.
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store)
    status = record_step(
        RecordStepRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            now=_Clock(),
            step_id="s1",
            verdict=StepVerdict.failed,
            command="pytest",
            output_sha256="c" * 64,
            output_excerpt="boom",
            exit_code=1,
        )
    )
    assert status is StepStatus.unverified
    assert store.read_provenance("u", root=tmp_path).steps[0].evidence is not None


# --- plan_steps: whole-plan replace carries surviving evidence (D-12) ---------


def test_plan_steps_replace_carries_surviving_evidence(tmp_path: Path) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store, step_id="s1", text="keep me")
    record_step(
        RecordStepRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            now=_Clock(),
            step_id="s1",
            verdict=StepVerdict.passed,
            command="pytest",
            output_sha256="d" * 64,
            output_excerpt="ok",
            exit_code=0,
        )
    )
    # Whole-plan replace: the surviving step keeps its evidence; a changed step
    # (same id, new text) derives unverified.
    plan_steps(
        PlanStepsRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            now=_Clock(),
            steps=[
                Step(id="s1", text="keep me"),
                Step(id="s2", text="brand new"),
            ],
        )
    )
    prov = store.read_provenance("u", root=tmp_path)
    survivor = next(s for s in prov.steps if s.id == "s1")
    fresh = next(s for s in prov.steps if s.id == "s2")
    assert derive_step_status(survivor) is StepStatus.resolved
    assert fresh.evidence is None


def test_plan_steps_replace_drops_evidence_on_edited_text(tmp_path: Path) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store, step_id="s1", text="original text")
    record_step(
        RecordStepRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            now=_Clock(),
            step_id="s1",
            verdict=StepVerdict.passed,
            command="pytest",
            output_sha256="e" * 64,
            output_excerpt="ok",
            exit_code=0,
        )
    )
    plan_steps(
        PlanStepsRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            now=_Clock(),
            steps=[Step(id="s1", text="EDITED text")],
        )
    )
    prov = store.read_provenance("u", root=tmp_path)
    assert prov.steps[0].evidence is None


# --- macro-gate: draft refuses over unresolved steps -------------------------


@pytest.mark.asyncio
async def test_draft_refuses_over_unresolved_step(tmp_path: Path) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store)  # planned, no evidence → unresolved
    with pytest.raises(EvidenceIncompleteError):
        await draft(_request(tmp_path, store))
    assert not (tmp_path / "docs" / "u.md").exists()
    assert store.read_provenance("u", root=tmp_path).generations == []


@pytest.mark.asyncio
async def test_draft_allows_resolved_steps(tmp_path: Path) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    text = "run the check"
    prov = store.read_provenance("u", root=tmp_path)
    prov.steps = [Step(id="s1", text=text, evidence=_resolved_evidence(text))]
    store.write_provenance(prov, root=tmp_path)
    path = (await draft(_request(tmp_path, store))).path
    assert path.exists()


@pytest.mark.asyncio
async def test_step_free_unit_drafts_and_seals(tmp_path: Path) -> None:
    # EVID-06: a step-free unit never takes the evidence path — drafts and seals.
    store = _seed_unit(tmp_path, with_steering=True)
    assert (await draft(_request(tmp_path, store))).path.exists()
    outcome = review(_accept_request(tmp_path, store))
    assert outcome.state is ProgressState.reviewed
    prov = store.read_provenance("u", root=tmp_path)
    assert prov.reviewer_edits[-1].verdict is ReviewVerdict.accept


# --- gate ordering: signoff → evidence → lease (D-10) ------------------------


@pytest.mark.asyncio
async def test_gate_order_signoff_precedes_evidence(tmp_path: Path) -> None:
    # An unsigned unit that ALSO has an unresolved step surfaces the signoff
    # refusal first — signoff sits upstream of the evidence gate.
    store = _seed_unit(tmp_path, with_steering=False)
    prov = store.read_provenance("u", root=tmp_path)
    prov.steps = [Step(id="s1", text="x")]
    store.write_provenance(prov, root=tmp_path)
    with pytest.raises(SignoffRequiredError):
        await draft(_request(tmp_path, store))


@pytest.mark.asyncio
async def test_gate_order_evidence_precedes_lease(tmp_path: Path) -> None:
    # A signed unit with an unresolved step AND a claimed target surfaces the
    # evidence refusal before the lease re-check ever runs.
    store = _seed_unit(tmp_path, with_steering=True)
    _plan_one_step(tmp_path, store)

    class _LeaseExplodes(FilesystemPlanningStore):
        def assert_draft_targets_unclaimed(
            self, unit_id: str, targets: list[str], *, root: Path
        ) -> None:
            raise AssertionError("lease re-check reached before the evidence gate")

    request = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=MockDraftingProvider(),
        store=_LeaseExplodes(),
        provider_name="mock",
        now=_Clock(),
    )
    with pytest.raises(EvidenceIncompleteError):
        await draft(request)


@pytest.mark.asyncio
async def test_lease_runs_after_evidence_passes(tmp_path: Path) -> None:
    # The companion to the ordering test: when steps resolve, control reaches the
    # lease re-check (here forced to refuse), proving the gate slots BETWEEN.
    store = _seed_unit(tmp_path, with_steering=True)
    text = "run the check"
    prov = store.read_provenance("u", root=tmp_path)
    prov.steps = [Step(id="s1", text=text, evidence=_resolved_evidence(text))]
    store.write_provenance(prov, root=tmp_path)

    class _LeaseClaimed(FilesystemPlanningStore):
        def assert_draft_targets_unclaimed(
            self, unit_id: str, targets: list[str], *, root: Path
        ) -> None:
            raise TargetClaimedError("page claimed by another in-flight unit")

    request = DraftRequest(
        unit_id="u",
        root=tmp_path,
        provider=MockDraftingProvider(),
        store=_LeaseClaimed(),
        provider_name="mock",
        now=_Clock(),
    )
    with pytest.raises(TargetClaimedError):
        await draft(request)


# --- seal-side macro-gate: accept refuses over post-draft-stale steps ---------


@pytest.mark.asyncio
async def test_review_accept_refuses_over_poststale_step(tmp_path: Path) -> None:
    # D-09 seal side: a step resolved at draft time that goes unresolved before
    # the accept refuses — nothing sealed, no reviewer edit appended.
    store = _seed_unit(tmp_path, with_steering=True)
    text = "run the check"
    prov = store.read_provenance("u", root=tmp_path)
    prov.steps = [Step(id="s1", text=text, evidence=_resolved_evidence(text))]
    store.write_provenance(prov, root=tmp_path)
    await draft(_request(tmp_path, store))  # succeeds (steps resolved)
    # Post-draft: the step goes unresolved (evidence cleared / edited away).
    prov = store.read_provenance("u", root=tmp_path)
    prov.steps[0].evidence = None
    store.write_provenance(prov, root=tmp_path)
    before = len(store.read_provenance("u", root=tmp_path).reviewer_edits)
    with pytest.raises(EvidenceIncompleteError):
        review(_accept_request(tmp_path, store))
    after = len(store.read_provenance("u", root=tmp_path).reviewer_edits)
    assert after == before  # no reviewer edit appended


@pytest.mark.asyncio
async def test_review_accept_seals_when_steps_resolved(tmp_path: Path) -> None:
    store = _seed_unit(tmp_path, with_steering=True)
    text = "run the check"
    prov = store.read_provenance("u", root=tmp_path)
    prov.steps = [Step(id="s1", text=text, evidence=_resolved_evidence(text))]
    store.write_provenance(prov, root=tmp_path)
    await draft(_request(tmp_path, store))
    outcome = review(_accept_request(tmp_path, store))
    assert outcome.state is ProgressState.reviewed
    assert (
        store.read_provenance("u", root=tmp_path).reviewer_edits[-1].verdict
        is ReviewVerdict.accept
    )
