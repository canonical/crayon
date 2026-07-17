"""Tests for ``derive_progress`` — the record-only lifecycle rule (PROV-04, D-05).

``derive_progress(provenance) -> ProgressState`` computes a unit's lifecycle state
from the provenance record alone. The count-based rule (D-05):

* empty ``generations``                               ⇒ ``pending``
* ``len(reviewer_edits) > latest.reviewer_edit_count`` ⇒ ``reviewed``
* otherwise                                            ⇒ ``drafted``

The final scenario (:func:`test_stale_progress_ignored`) is the record-side proof of
desync-impossibility: a divergent ``progress.yaml`` on disk can never change the
value derivation returns, because derivation reads only the in-memory provenance
record and never touches the filesystem.
"""

import hashlib

import yaml

from dogen.core.models import (
    Effort,
    FileDigest,
    Generation,
    ProgressState,
    Provenance,
    ReviewerEdit,
    Step,
    StepEvidence,
    StepMode,
    StepStatus,
    StepVerdict,
    all_steps_verified,
    derive_progress,
    derive_step_status,
)


def _generation(**overrides: object) -> Generation:
    """Construct a minimal valid :class:`Generation`, mirroring tests/test_models.py."""
    fields: dict = {
        "model": "gpt",
        "model_version": "x",
        "effort": Effort.medium,
        "tooling_version": "0.0.0",
        "sdk": "github-copilot-sdk==1.0.2",
        "files": [FileDigest(path="docs/reference/cli.md", sha256="ab12")],
        "run_id": "abc",
        "at": "2026-06-20T00:00:00Z",
        "action": "draft",
    }
    fields.update(overrides)
    return Generation(**fields)


def _reviewer_edit(**overrides: object) -> ReviewerEdit:
    """Construct a minimal valid :class:`ReviewerEdit`."""
    fields: dict = {
        "at": "2026-06-20T01:00:00Z",
        "reviewer": "Reviewer",
        "summary": "reviewed",
    }
    fields.update(overrides)
    return ReviewerEdit(**fields)


def test_pending_when_no_generations() -> None:
    prov = Provenance(unit_id="cli-usage")
    assert derive_progress(prov) is ProgressState.pending


def test_drafted_after_generation() -> None:
    prov = Provenance(
        unit_id="cli-usage",
        generations=[_generation(reviewer_edit_count=0)],
    )
    assert derive_progress(prov) is ProgressState.drafted


def test_reviewed_when_review_lands_after_draft() -> None:
    # One generation snapshotted 0 reviewer_edits; one review has since landed.
    # len(reviewer_edits)=1 > latest.reviewer_edit_count=0 ⇒ reviewed.
    prov = Provenance(
        unit_id="cli-usage",
        generations=[_generation(reviewer_edit_count=0)],
        reviewer_edits=[_reviewer_edit()],
    )
    assert derive_progress(prov) is ProgressState.reviewed


def test_redraft_after_fix_falls_back_to_drafted() -> None:
    # After a reviewed state (1 edit), a redraft snapshots the current edit count.
    # The new generation's reviewer_edit_count=1 == len(reviewer_edits)=1, so the
    # count is no longer strictly greater ⇒ drafted again.
    prov = Provenance(
        unit_id="cli-usage",
        generations=[
            _generation(reviewer_edit_count=0),
            _generation(reviewer_edit_count=1),
        ],
        reviewer_edits=[_reviewer_edit()],
    )
    assert derive_progress(prov) is ProgressState.drafted


def test_stale_progress_ignored(tmp_path) -> None:
    """Desync-impossibility scenario: a divergent on-disk progress.yaml is irrelevant.

    Replays the round-3 opencode ``workshop-definition`` desync shape
    (git 3 / provenance 3 / progress 2) that motivated PROV-04: three generations
    whose ``reviewer_edit_count`` snapshots are 0/1/2 and four landed reviewer_edits.
    len(reviewer_edits)=4 > latest.reviewer_edit_count=2 ⇒ the record derives
    ``reviewed``. We hand-construct the counts in-test for determinism rather than
    loading
    ``validation/round-3/opencode/.dogen/units/workshop-definition/`` — the fixture is
    only the shape reference. A DIVERGENT ``progress.yaml`` (schema_version 1,
    state ``pending``) is written next to the record on disk; derivation must still
    return the provenance-implied ``reviewed``, proving reads can never disagree with
    provenance because the function performs no I/O (D-05).
    """
    prov = Provenance(
        unit_id="workshop-definition",
        generations=[
            _generation(reviewer_edit_count=0),
            _generation(reviewer_edit_count=1),
            _generation(reviewer_edit_count=2),
        ],
        reviewer_edits=[
            _reviewer_edit(),
            _reviewer_edit(),
            _reviewer_edit(),
            _reviewer_edit(),
        ],
    )

    # Write a stale, divergent progress.yaml on disk next to the record. Its state
    # (pending) contradicts the provenance-derived state (reviewed) on purpose.
    unit_dir = tmp_path / ".dogen" / "units" / "workshop-definition"
    unit_dir.mkdir(parents=True)
    stale_progress = unit_dir / "progress.yaml"
    stale_progress.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "unit_id": "workshop-definition",
                "state": "pending",
                "history": [],
            }
        )
    )

    # Derivation reads only the record; the divergent on-disk file cannot change it.
    assert derive_progress(prov) is ProgressState.reviewed
    assert "pending" in stale_progress.read_text()  # the disk file is truly stale


# --- Phase 12: derive_step_status / all_steps_verified (EVID-03) ---


def _sha256_text(text: str) -> str:
    """The step-text hashing discipline mirrored for test fixtures (D-02)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _step_with_evidence(text: str = "run tests", **ev_overrides: object) -> Step:
    """A step whose evidence's step_text_sha256 matches ``text`` (a fresh capture)."""
    ev_fields: dict = {
        "mode": StepMode.agent,
        "command": "uv run pytest",
        "output_sha256": "outhash",
        "output_excerpt": "ok",
        "exit_code": 0,
        "verdict": StepVerdict.passed,
        "step_text_sha256": _sha256_text(text),
        "at": "2026-07-17T00:00:00Z",
    }
    ev_fields.update(ev_overrides)
    return Step(id="s1", text=text, evidence=StepEvidence(**ev_fields))


def test_step_without_evidence_is_unverified() -> None:
    # Default-FAIL: no evidence never resolves.
    assert derive_step_status(Step(id="s1", text="run tests")) is StepStatus.unverified


def test_step_with_stale_text_hash_is_unverified() -> None:
    # D-02: editing the step text after capture rebinds to default-FAIL.
    step = _step_with_evidence(text="run tests")
    edited = step.model_copy(update={"text": "run the OTHER tests"})
    assert derive_step_status(edited) is StepStatus.unverified


def test_passed_evidence_resolves() -> None:
    step = _step_with_evidence(verdict=StepVerdict.passed)
    assert derive_step_status(step) is StepStatus.resolved


def test_skipped_with_reason_resolves() -> None:
    # D-07: a consciously-skipped step (with reason) resolves.
    step = _step_with_evidence(verdict=StepVerdict.skipped, reason="not applicable")
    assert derive_step_status(step) is StepStatus.resolved


def test_skipped_without_reason_is_unverified() -> None:
    step = _step_with_evidence(verdict=StepVerdict.skipped, reason="")
    assert derive_step_status(step) is StepStatus.unverified


def test_deviated_with_zero_exit_resolves() -> None:
    # D-08: a divergence resolves only when the capture shows success.
    step = _step_with_evidence(verdict=StepVerdict.deviated, exit_code=0)
    assert derive_step_status(step) is StepStatus.resolved


def test_deviated_with_nonzero_exit_is_unverified() -> None:
    step = _step_with_evidence(verdict=StepVerdict.deviated, exit_code=1)
    assert derive_step_status(step) is StepStatus.unverified


def test_failed_never_resolves() -> None:
    # D-07: fail never resolves, even with a zero exit code payload.
    step = _step_with_evidence(verdict=StepVerdict.failed, exit_code=0)
    assert derive_step_status(step) is StepStatus.unverified


def test_all_steps_verified_vacuously_true_for_no_steps() -> None:
    # EVID-06 keystone: a step-free unit is never blocked by the evidence gate.
    assert all_steps_verified(Provenance(unit_id="u")) is True


def test_all_steps_verified_false_when_any_step_unverified() -> None:
    resolved = _step_with_evidence(verdict=StepVerdict.passed)
    unresolved = Step(id="s2", text="unproven")  # no evidence
    prov = Provenance(unit_id="u", steps=[resolved, unresolved])
    assert all_steps_verified(prov) is False


def test_all_steps_verified_true_when_every_step_resolves() -> None:
    s1 = _step_with_evidence(text="step a", verdict=StepVerdict.passed)
    s2 = _step_with_evidence(text="step b", verdict=StepVerdict.skipped, reason="n/a")
    prov = Provenance(unit_id="u", steps=[s1, s2])
    assert all_steps_verified(prov) is True
