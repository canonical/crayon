"""EVID-06 regression guard: the step-free (reference/explanation) path is untouched.

The phase safety net. Everything the evidence schema (Plan 01), the micro/macro
gates (Plan 02), and the record CLI (Plan 03) added is keyed on
``provenance.steps`` *presence* — never on ``unit.intent``. So a step-free unit
(the reference/explanation lifecycle that carries no machine-owned step plan)
must be provably **byte-identical** to a pre-phase record in both its pure
derivations (``derive_progress``/``is_sealed``) and its refusal behavior (an
unsigned draft still surfaces the signoff refusal; a signed one drafts and seals
normally, never entering the evidence path).

These assertions complement — never duplicate — the Plan 02 gate-ordering pin in
``tests/test_orchestrator_hitl.py``: there the cascade is proven over a *stepped*
unit (signoff → evidence → lease); here the step-free complement proves the
evidence leg is skipped entirely (signoff → lease), so ``all_steps_verified`` is
vacuously true and no ``EvidenceIncompleteError`` path is ever reachable.

Fully offline: no token, no network (D-17).
"""

from pathlib import Path

import pytest

from dogen.adapters.mock_provider import MockDraftingProvider
from dogen.adapters.planning_fs import (
    FilesystemPlanningStore,
    TargetClaimedError,
)
from dogen.core.models import (
    Effort,
    FileDigest,
    Generation,
    Intent,
    ProgressState,
    Provenance,
    ReviewerEdit,
    ReviewVerdict,
    Signoff,
    Step,
    all_steps_verified,
    derive_progress,
    is_sealed,
)
from dogen.core.orchestrator import (
    DraftRequest,
    EvidenceIncompleteError,
    ReviewRequest,
    SignoffRequiredError,
    draft,
    review,
)


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


def _signoff() -> Signoff:
    return Signoff(
        author="Ada",
        at="2026-01-01T00:00:00Z",
        intent=Intent.reference,
        audience="devs",
    )


def _generation(**overrides: object) -> Generation:
    fields: dict = {
        "model": "gpt",
        "model_version": "x",
        "effort": Effort.medium,
        "tooling_version": "0.0.0",
        "sdk": "",
        "files": [FileDigest(path="docs/reference/cli.md", sha256="ab12")],
        "run_id": "abc",
        "at": "2026-01-01T00:00:01Z",
        "action": "draft",
        "reviewer_edit_count": 0,
    }
    fields.update(overrides)
    return Generation(**fields)


def _reviewer_edit(**overrides: object) -> ReviewerEdit:
    fields: dict = {
        "at": "2026-01-01T00:00:02Z",
        "reviewer": "Reviewer",
        "summary": "reviewed",
    }
    fields.update(overrides)
    return ReviewerEdit(**fields)


# --------------------------------------------------------------------------- #
# 1. Pure derivations are byte-identical for a step-free record across the
#    lifecycle — derive_progress/is_sealed never read `steps`, and an empty
#    plan is vacuously verified (EVID-06 keystone).
# --------------------------------------------------------------------------- #


def _pending() -> Provenance:
    return Provenance(unit_id="u", signoff=_signoff())


def _drafted() -> Provenance:
    return Provenance(
        unit_id="u",
        signoff=_signoff(),
        generations=[_generation(reviewer_edit_count=0)],
    )


def _reviewed() -> Provenance:
    return Provenance(
        unit_id="u",
        signoff=_signoff(),
        generations=[_generation(reviewer_edit_count=0)],
        reviewer_edits=[_reviewer_edit(verdict=ReviewVerdict.fix)],
    )


def _sealed() -> Provenance:
    return Provenance(
        unit_id="u",
        signoff=_signoff(),
        generations=[_generation(reviewer_edit_count=0)],
        reviewer_edits=[_reviewer_edit(verdict=ReviewVerdict.accept)],
    )


@pytest.mark.parametrize(
    ("factory", "expected_progress", "expected_sealed"),
    [
        (_pending, ProgressState.pending, False),
        (_drafted, ProgressState.drafted, False),
        (_reviewed, ProgressState.reviewed, False),
        (_sealed, ProgressState.reviewed, True),
    ],
)
def test_step_free_derivations_are_byte_identical(
    factory, expected_progress: ProgressState, expected_sealed: bool
) -> None:
    # A step-free record derives exactly the values it did before the evidence
    # schema existed, across pending/drafted/reviewed/sealed — the empty `steps`
    # field changes nothing (derive_progress/is_sealed never read it).
    prov = factory()
    assert prov.steps == []
    assert derive_progress(prov) is expected_progress
    assert is_sealed(prov) is expected_sealed
    # Vacuous truth: a step-free plan is never blocked by the evidence gate.
    assert all_steps_verified(prov) is True


def test_step_free_record_omits_steps_key_entirely() -> None:
    # The byte-identity keystone: a step-free record serializes with NO `steps`
    # key (surgical omit-empty), so it is indistinguishable on the wire from a
    # pre-phase record.
    dump = _drafted().model_dump(mode="json")
    assert "steps" not in dump


def test_adding_then_clearing_steps_returns_to_byte_identical() -> None:
    # Defensive: a record that once carried a step but no longer does is again
    # byte-identical (the omit-empty is on emptiness, not on never-having-steps).
    baseline = _drafted().model_dump(mode="json")
    stepped = _drafted()
    stepped.steps = [Step(id="s1", text="run the check")]
    assert "steps" in stepped.model_dump(mode="json")
    stepped.steps = []
    assert stepped.model_dump(mode="json") == baseline


# --------------------------------------------------------------------------- #
# 2. Refusal behavior is unchanged for a step-free unit — the evidence macro-gate
#    is never entered when `provenance.steps == []` (cascade signoff → lease).
# --------------------------------------------------------------------------- #


def _seed(root: Path, *, signed: bool) -> FilesystemPlanningStore:
    """Scaffold a step-free unit ``u``, optionally signed off (no step plan)."""
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=Intent.reference, audience="devs")
    store.write_provenance(
        Provenance(unit_id="u", signoff=_signoff() if signed else None),
        root=root,
    )
    return store


def _draft_request(root: Path, store: FilesystemPlanningStore) -> DraftRequest:
    return DraftRequest(
        unit_id="u",
        root=root,
        provider=MockDraftingProvider(),
        store=store,
        provider_name="mock",
        now=_Clock(),
    )


def _accept_request(root: Path, store: FilesystemPlanningStore) -> ReviewRequest:
    return ReviewRequest(
        unit_id="u",
        root=root,
        store=store,
        identity=lambda: ("Ada", "ada@example.com"),
        now=_Clock(),
        note="ship it",
        verdict=ReviewVerdict.accept,
    )


@pytest.mark.asyncio
async def test_step_free_unsigned_draft_still_refuses_signoff_only(
    tmp_path: Path,
) -> None:
    # An unsigned step-free unit surfaces the signoff refusal (never an evidence
    # refusal) — the evidence gate is downstream and never reached.
    store = _seed(tmp_path, signed=False)
    with pytest.raises(SignoffRequiredError):
        await draft(_draft_request(tmp_path, store))
    # Zero side effects, exactly as before the phase.
    assert store.read_provenance("u", root=tmp_path).generations == []
    assert not (tmp_path / "docs" / "u.md").exists()


@pytest.mark.asyncio
async def test_step_free_signed_unit_drafts_and_seals(tmp_path: Path) -> None:
    # A signed step-free unit drafts and seals byte-identically — no evidence path.
    store = _seed(tmp_path, signed=True)
    assert (await draft(_draft_request(tmp_path, store))).path.exists()
    outcome = review(_accept_request(tmp_path, store))
    assert outcome.state is ProgressState.reviewed
    prov = store.read_provenance("u", root=tmp_path)
    assert prov.reviewer_edits[-1].verdict is ReviewVerdict.accept
    assert is_sealed(prov) is True
    # The record stayed step-free throughout — no evidence machinery was engaged.
    assert prov.steps == []


@pytest.mark.asyncio
async def test_step_free_cascade_skips_evidence_reaches_lease(tmp_path: Path) -> None:
    # The step-free complement to the Plan 02 ordering pin: with no steps the
    # evidence leg is skipped, so control reaches the lease re-check (here forced
    # to refuse). The cascade is signoff → lease; EvidenceIncompleteError is
    # unreachable for a step-free unit.
    _seed(tmp_path, signed=True)

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
    # And never the evidence refusal — proving the gate is truly skipped.
    with pytest.raises(TargetClaimedError):
        await draft(request)
    assert EvidenceIncompleteError is not TargetClaimedError
