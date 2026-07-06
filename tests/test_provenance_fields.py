"""Provenance-truth tests for the provider-reported ``sdk``/``mode`` fields.

Phase 03 Plan 01 (D-14/D-12): the recorded ``sdk`` and ``mode`` must be
*provider-reported*, not unconditional module constants. These tests lock the
honest defaults and the mock's driver identity so the SDK-free mock can never
again fabricate ``github-copilot-sdk==1.0.2`` / ``local`` provenance (T-03-03).
"""

import pytest

from dogen.adapters.mock_provider import MockDraftingProvider
from dogen.core.models import (
    SCHEMA_VERSION,
    DraftResult,
    Intent,
    Provenance,
    Signoff,
    SourceRef,
)


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
