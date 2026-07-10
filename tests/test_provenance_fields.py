"""Provenance-truth tests for the provider-reported ``sdk``/``mode`` fields.

Phase 03 Plan 01 (D-14/D-12): the recorded ``sdk`` and ``mode`` must be
*provider-reported*, not unconditional module constants. These tests lock the
honest defaults and the mock's driver identity so the SDK-free mock can never
again fabricate ``github-copilot-sdk==1.0.2`` / ``local`` provenance (T-03-03).
"""

import importlib

import pytest

from dogen.adapters.mock_provider import MockDraftingProvider
from dogen.core.models import (
    SCHEMA_VERSION,
    DraftResult,
    Generation,
    Intent,
    Provenance,
    ReviewerEdit,
    Signoff,
    SourceRef,
)


def _generation(**overrides: object) -> Generation:
    fields: dict = {
        "model": "m",
        "model_version": "v",
        "effort": None,
        "tooling_version": "0.0.0",
        "sdk": "s",
        "run_id": "r",
        "at": "2026-01-01T00:00:00Z",
        "action": "draft",
        "files": [{"path": "docs/a.md", "sha256": "ab12"}],
    }
    fields.update(overrides)
    return Generation.model_validate(fields)


def test_draft_result_defaults_sdk_and_mode_empty() -> None:
    # A bare DraftResult carries honest empty defaults — no SDK id and no run
    # mode are asserted unless a provider reports them (D-14/D-12).
    result = DraftResult(text="body", model="m", output_tokens=1, run_id="")
    assert result.sdk == ""
    assert result.mode == ""


@pytest.mark.asyncio
async def test_mock_provider_reports_driver_mode_and_empty_sdk() -> None:
    # The deterministic mock is an in-process *driver* double (D-12): it reports
    # mode="driver" and, being SDK-free, sdk="" — never the copilot SDK id.
    steering = Signoff(
        author="ta",
        at="2026-07-02T00:00:00Z",
        intent=Intent.reference,
        audience="devs",
    )
    result = await MockDraftingProvider().draft_unit(
        intent=Intent.reference,
        audience="devs",
        signoff=steering,
        sources=[SourceRef(path="README.md")],
    )
    assert result.sdk == ""
    assert result.mode == "driver"


def test_provenance_schema_version_is_current() -> None:
    # v1: the steering split (signoff + stream) is an explicit, versioned
    # migration — records now stamp the current schema generation.
    assert Provenance(unit_id="u").schema_version == SCHEMA_VERSION


# --- Phase 5: schema v2 field disposition (PROV-01/PROV-02) --------------------


def test_deleted_legacy_fields_absent_from_v2_models() -> None:
    assert "draft_path" not in Generation.model_fields
    assert "draft_sha256" not in Generation.model_fields
    assert "draft_sha256" not in ReviewerEdit.model_fields
    assert "verification" not in Provenance.model_fields
    # The verification block classes are gone — `from dogen.core.models import
    # Verification` would raise ImportError (asserted here as absence).
    models = importlib.import_module("dogen.core.models")
    assert not hasattr(models, "Verification")
    assert not hasattr(models, "VerificationStep")


def test_generation_omits_empty_effort_model_version_sdk_no_over_drop() -> None:
    gen = _generation(effort=None, model_version="", sdk="", gaps_note="")
    dump = gen.model_dump(mode="json")
    assert "effort" not in dump
    assert "model_version" not in dump
    assert "sdk" not in dump
    # No over-drop: an unrelated empty field stays present.
    assert "gaps_note" in dump
    assert "files" in dump


def test_generation_retains_non_empty_omit_fields() -> None:
    gen = _generation(effort="medium", model_version="1.2", sdk="copilot")
    dump = gen.model_dump(mode="json")
    assert dump["effort"] == "medium"
    assert dump["model_version"] == "1.2"
    assert dump["sdk"] == "copilot"


def test_generation_model_origin_defaults_empty() -> None:
    assert _generation().model_origin == ""
