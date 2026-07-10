"""Behaviour tests for the F1 planning-directory schema v1 (core/models.py)."""

import copy

import pytest
from pydantic import ValidationError

from dogen.core.models import (
    SCHEMA_VERSION,
    Effort,
    FileDigest,
    Generation,
    Intent,
    Progress,
    ProgressEntry,
    ProgressState,
    Provenance,
    ReadRecord,
    ReviewerEdit,
    Signoff,
    SourceRef,
    Unit,
)


def _valid_front_matter() -> dict:
    return {
        "unit_id": "cli-usage",
        "intent": "reference",
        "audience": "developers",
        "title": "dogen CLI usage",
        "sources": [{"path": "src/dogen/cli/main.py"}],
        "sphinx_target": "reference/cli.md",
        "steering_notes": "Document the four subcommands.",
        "status": "pending",
    }


def test_unit_round_trips_front_matter() -> None:
    unit = Unit(**_valid_front_matter())
    assert unit.intent is Intent.reference
    assert unit.audience == "developers"
    assert unit.title == "dogen CLI usage"
    assert unit.sources[0].path == "src/dogen/cli/main.py"
    assert unit.sphinx_target == "reference/cli.md"
    assert unit.steering_notes == "Document the four subcommands."


def test_unit_rejects_invalid_intent() -> None:
    bad = _valid_front_matter()
    bad["intent"] = "marketing"
    with pytest.raises(ValidationError):
        Unit(**bad)


def test_intent_has_exactly_the_four_diataxis_directions() -> None:
    assert {m.value for m in Intent} == {
        "reference",
        "tutorial",
        "how-to",
        "explanation",
    }


def test_effort_includes_xhigh() -> None:
    assert Effort.xhigh.value == "xhigh"
    assert {m.value for m in Effort} == {"low", "medium", "high", "xhigh"}


def test_machine_models_default_schema_version_current() -> None:
    assert Unit(**_valid_front_matter()).schema_version == SCHEMA_VERSION
    assert Provenance(unit_id="cli-usage").schema_version == SCHEMA_VERSION
    assert (
        Progress(
            unit_id="cli-usage",
            state=ProgressState.pending,
            history=[],
        ).schema_version
        == SCHEMA_VERSION
    )


def test_provenance_reserves_empty_reviewer_edits_and_generations() -> None:
    # v2: the reserved-empty ``verification`` block was deleted (PROV-02); a
    # scaffold-time record simply carries empty streams.
    prov = Provenance(unit_id="cli-usage")
    assert prov.reviewer_edits == []
    assert prov.generations == []
    assert prov.signoff is None
    assert prov.steering == []


def test_progress_accepts_lifecycle_ordering_in_history() -> None:
    order = [
        ProgressState.pending,
        ProgressState.sourced,
        ProgressState.drafted,
        ProgressState.reviewed,
        ProgressState.committed,
    ]
    progress = Progress(
        unit_id="cli-usage",
        state=ProgressState.drafted,
        history=[ProgressEntry(at="2026-06-20T00:00:00Z", state=s) for s in order],
    )
    assert [e.state for e in progress.history] == order


def test_committed_exists_in_enum_but_no_setter_helper() -> None:
    assert ProgressState.committed.value == "committed"
    # The schema exposes no method that advances a Progress to committed; the
    # gate lives in the orchestrator (plan 02). Guard against a helper slipping in.
    assert not any(
        callable(getattr(Progress, name, None)) and "commit" in name.lower()
        for name in dir(Progress)
    )


def test_sources_and_context_origins_are_distinct_fields() -> None:
    unit = Unit(**_valid_front_matter())
    gen = Generation(
        model="gpt",
        model_version="x",
        effort=Effort.medium,
        tooling_version="0.0.0",
        sdk="github-copilot-sdk==1.0.2",
        context_origins=["AGENTS.md"],  # ty: ignore[invalid-argument-type]
        tools_used=["builtin:grep"],
        files=[FileDigest(path="docs/reference/cli.md", sha256="ab12")],
        run_id="abc",
        at="2026-06-20T00:00:00Z",
        action="draft",
    )
    assert [s.path for s in unit.sources] == ["src/dogen/cli/main.py"]
    # v1: plain-string origins are lifted to commit-stampable ReadRecords.
    assert [o.path for o in gen.context_origins] == ["AGENTS.md"]
    # Mutating one never touches the other (different objects, different fields).
    gen.context_origins.append(ReadRecord(path="README.md"))
    assert [s.path for s in unit.sources] == ["src/dogen/cli/main.py"]


def _generation(**overrides: object) -> Generation:
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


def test_generation_provider_mode_default_empty_and_round_trip() -> None:
    # OQ-1: provider/mode are additive provenance fields with empty defaults.
    default = _generation()
    assert default.provider == ""
    assert default.mode == ""

    stamped = _generation(provider="mock", mode="local")
    dump = stamped.model_dump()
    assert dump["provider"] == "mock"
    assert dump["mode"] == "local"
    assert Generation(**dump).provider == "mock"
    assert Generation(**dump).mode == "local"

    assert Provenance(unit_id="cli-usage").schema_version == SCHEMA_VERSION


def test_source_ref_is_path_xor_ref() -> None:
    assert SourceRef(path="a.py").ref is None
    assert SourceRef(ref="docpr-2845").path is None
    with pytest.raises(ValidationError):
        SourceRef(path="a.py", ref="docpr-2845")
    with pytest.raises(ValidationError):
        SourceRef()


def test_steering_records_the_hitl_event_fields() -> None:
    steering = Signoff(
        author="Ada <ada@example.com>",
        at="2026-06-20T00:00:00Z",
        intent=Intent.reference,
        audience="developers",
    )
    assert steering.intent is Intent.reference
    assert steering.audience == "developers"


def test_provenance_migrates_v0_steering_mapping_to_signoff() -> None:
    prov = Provenance(
        unit_id="cli-usage",
        schema_version=0,
        steering={  # ty: ignore[invalid-argument-type]
            "author": "Ada",
            "at": "2026-06-20T00:00:00Z",
            "intent": "reference",
            "audience": "developers",
        },
    )
    assert prov.signoff is not None
    assert prov.signoff.author == "Ada"
    assert prov.signoff.plan_hash == ""
    assert prov.steering == []
    assert prov.schema_version == SCHEMA_VERSION


# --- Phase 5: schema v2 migration (PROV-01/PROV-02/PROV-03) --------------------


def _legacy_generation(**overrides: object) -> dict:
    """A raw v1 legacy-only generation dict (draft_path/draft_sha256, no files)."""
    gen: dict = {
        "model": "m",
        "model_version": "v",
        "effort": "medium",
        "tooling_version": "0.0.0",
        "sdk": "",
        "run_id": "r",
        "at": "2026-01-01T00:00:00Z",
        "action": "draft",
        "draft_path": "docs/a.md",
        "draft_sha256": "ab12",
    }
    gen.update(overrides)
    return gen


def test_migrates_v1_legacy_only_generation_synthesizes_files() -> None:
    raw = {
        "unit_id": "u",
        "schema_version": 1,
        "generations": [_legacy_generation()],
    }
    prov = Provenance.model_validate(raw)
    assert prov.schema_version == SCHEMA_VERSION
    gen = prov.generations[0]
    assert [(f.path, f.sha256) for f in gen.files] == [("docs/a.md", "ab12")]
    assert not hasattr(gen, "draft_path")
    assert not hasattr(gen, "draft_sha256")


def test_migrates_v1_2_dual_field_disagreement_prefers_files() -> None:
    raw = {
        "unit_id": "u",
        "schema_version": 1,
        "generations": [
            _legacy_generation(
                files=[{"path": "docs/a.md", "sha256": "files_wins"}],
                draft_sha256="legacy_loses",
            )
        ],
    }
    prov = Provenance.model_validate(raw)
    gen = prov.generations[0]
    assert [(f.path, f.sha256) for f in gen.files] == [("docs/a.md", "files_wins")]
    assert not hasattr(gen, "draft_sha256")


def test_migrates_reviewer_edit_borrows_path_from_paired_generation() -> None:
    raw = {
        "unit_id": "u",
        "schema_version": 1,
        "generations": [
            _legacy_generation(draft_path="docs/a.md", draft_sha256="ab12")
        ],
        "reviewer_edits": [
            {
                "at": "2026-01-01T00:01:00Z",
                "reviewer": "rev",
                "summary": "ok",
                "verdict": "accept",
                "draft_sha256": "ab12",
            }
        ],
    }
    prov = Provenance.model_validate(raw)
    edit = prov.reviewer_edits[0]
    assert [(f.path, f.sha256) for f in edit.files] == [("docs/a.md", "ab12")]
    assert not hasattr(edit, "draft_sha256")


def test_migrates_non_accept_reviewer_edit_to_empty_files() -> None:
    raw = {
        "unit_id": "u",
        "schema_version": 1,
        "generations": [_legacy_generation()],
        "reviewer_edits": [
            {
                "at": "2026-01-01T00:01:00Z",
                "reviewer": "rev",
                "summary": "redo",
                "verdict": "redraft",
                "draft_sha256": "",
            }
        ],
    }
    prov = Provenance.model_validate(raw)
    assert prov.reviewer_edits[0].files == []


def test_v2_record_round_trips_unchanged_idempotent() -> None:
    v2 = {
        "unit_id": "u",
        "schema_version": SCHEMA_VERSION,
        "generations": [
            {
                "model": "m",
                "model_version": "v",
                "effort": "medium",
                "tooling_version": "0.0.0",
                "sdk": "sdk",
                "model_origin": "ta",
                "files": [{"path": "docs/a.md", "sha256": "ab12"}],
                "run_id": "r",
                "at": "2026-01-01T00:00:00Z",
                "action": "draft",
            }
        ],
    }
    prov = Provenance.model_validate(v2)
    dump = prov.model_dump(mode="json")
    again = Provenance.model_validate(dump)
    assert again.model_dump(mode="json") == dump
    assert again.schema_version == SCHEMA_VERSION


def test_migrator_does_not_mutate_input_dict() -> None:
    raw = {
        "unit_id": "u",
        "schema_version": 1,
        "generations": [_legacy_generation()],
    }
    snapshot = copy.deepcopy(raw)
    Provenance.model_validate(raw)
    assert raw == snapshot


def test_generation_files_invariant_requires_one_entry() -> None:
    with pytest.raises(ValidationError):
        Generation.model_validate(
            {
                "model": "m",
                "model_version": "v",
                "effort": None,
                "tooling_version": "0.0.0",
                "sdk": "",
                "run_id": "r",
                "at": "2026-01-01T00:00:00Z",
                "action": "draft",
            }
        )


def test_migration_bare_generation_without_digest_raises() -> None:
    raw = {
        "unit_id": "u",
        "schema_version": 1,
        "generations": [
            {
                "model": "m",
                "model_version": "v",
                "effort": "medium",
                "tooling_version": "0.0.0",
                "sdk": "",
                "run_id": "r",
                "at": "2026-01-01T00:00:00Z",
                "action": "draft",
            }
        ],
    }
    with pytest.raises(ValidationError):
        Provenance.model_validate(raw)


def test_reviewer_edit_files_digest_shape() -> None:
    edit = ReviewerEdit.model_validate(
        {
            "at": "2026-01-01T00:01:00Z",
            "reviewer": "rev",
            "summary": "ok",
            "verdict": "accept",
            "files": [{"path": "docs/a.md", "sha256": "ab12"}],
        }
    )
    assert [(f.path, f.sha256) for f in edit.files] == [("docs/a.md", "ab12")]
