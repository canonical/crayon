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

import yaml

from dogen.core.models import (
    Effort,
    FileDigest,
    Generation,
    ProgressState,
    Provenance,
    ReviewerEdit,
    derive_progress,
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
