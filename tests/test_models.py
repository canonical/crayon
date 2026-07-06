"""Behaviour tests for the F1 planning-directory schema v1 (core/models.py)."""

import pytest
from pydantic import ValidationError

from dogen.core.models import (
    SCHEMA_VERSION,
    Effort,
    Generation,
    Intent,
    Progress,
    ProgressEntry,
    ProgressState,
    Provenance,
    ReadRecord,
    Signoff,
    SourceRef,
    Unit,
    VerificationStep,
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


def test_provenance_reserves_empty_verification_and_reviewer_edits() -> None:
    prov = Provenance(unit_id="cli-usage")
    assert prov.verification.steps == []
    assert prov.reviewer_edits == []
    assert prov.generations == []
    assert prov.signoff is None
    assert prov.steering == []


def test_verification_step_defaults_are_reserved_empty() -> None:
    step = VerificationStep(id="build")
    assert step.state == "unverified"
    assert step.evidence is None
    assert step.env_fingerprint is None


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
