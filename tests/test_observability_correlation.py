"""Observability layer, mock provider, and provider-selection behaviour.

Covers Task 1: the OTel-API tracer/run_id helpers, the import discipline that
keeps ``core/observability.py`` free of ``logfire``/``opentelemetry.sdk``, the
deterministic SDK-free mock provider, and the by-name provider dispatch.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from dogen.adapters.mock_provider import MockDraftingProvider, select_provider
from dogen.core import observability
from dogen.core.models import Intent, Signoff, SourceRef
from dogen.obs import logfire_backend


@pytest.fixture
def in_memory_spans() -> InMemorySpanExporter:
    """Install a test-only in-memory OTel SDK exporter and return it.

    The core stays API-only; the SDK lives only in this test fixture so spans
    become inspectable. OTel forbids replacing an already-set global provider,
    so the override guard is reset to make this fixture order-independent
    (coding-guide §4: tests pass in any order).
    """
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # noqa: SLF001
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


def _steering() -> Signoff:
    return Signoff(
        author="Ada Lovelace",
        at="2026-01-01T00:00:00Z",
        intent=Intent.reference,
        audience="devs",
    )


def test_get_tracer_returns_otel_tracer() -> None:
    tracer = observability.get_tracer()
    assert hasattr(tracer, "start_as_current_span")


def test_draft_span_yields_32hex_run_id(in_memory_spans: InMemorySpanExporter) -> None:
    with observability.draft_span() as (span, run_id):
        assert len(run_id) == 32
        assert all(c in "0123456789abcdef" for c in run_id)
        assert run_id == format(span.get_span_context().trace_id, "032x")


def test_run_id_matches_exported_span(in_memory_spans: InMemorySpanExporter) -> None:
    with observability.draft_span() as (_span, run_id):
        pass
    finished = in_memory_spans.get_finished_spans()
    assert len(finished) == 1
    assert format(finished[0].context.trace_id, "032x") == run_id


def test_observability_imports_no_backend() -> None:
    source = Path(observability.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(
        name == "logfire" or name.startswith("logfire.") for name in imported
    )
    assert "opentelemetry.sdk" not in imported
    assert not any(name.startswith("opentelemetry.sdk") for name in imported)


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic() -> None:
    provider = MockDraftingProvider()
    steering = _steering()
    sources = [SourceRef(path="README.md")]
    first = await provider.draft_unit(
        intent=Intent.reference, audience="devs", signoff=steering, sources=sources
    )
    second = await provider.draft_unit(
        intent=Intent.reference, audience="devs", signoff=steering, sources=sources
    )
    assert first.text == second.text
    assert first.model == "mock-model"
    assert first.output_tokens == second.output_tokens
    assert first.text.startswith("# Reference for devs")


def test_mock_module_imports_no_sdk() -> None:
    source = Path(MockDraftingProvider.__module__.replace(".", "/"))
    path = Path("src") / source.with_suffix(".py")
    text = path.read_text(encoding="utf-8")
    assert "from copilot" not in text
    assert "import copilot" not in text
    assert "github_copilot_sdk" not in text


def test_select_provider_mock_does_not_import_copilot_adapter() -> None:
    sys.modules.pop("dogen.adapters.copilot.provider", None)
    provider = select_provider("mock")
    assert isinstance(provider, MockDraftingProvider)
    assert "dogen.adapters.copilot.provider" not in sys.modules


def test_select_provider_default_is_auto() -> None:
    # D-06: the default provider is now ``auto`` (offline-resolved to
    # copilot/host-harness), retiring the earlier hardcoded ``copilot`` default.
    assert inspect.signature(select_provider).parameters["name"].default == "auto"


def test_select_provider_copilot_resolves_real_adapter() -> None:
    # The copilot branch resolves the real adapter (lifted in Plan 03-02) via a
    # lazy import, kept function-local so the sibling mock-path no-import test
    # stays valid.
    from dogen.adapters.copilot import (  # noqa: PLC0415
        CopilotDraftingProvider,
    )

    provider = select_provider("copilot")
    assert isinstance(provider, CopilotDraftingProvider)


def test_select_provider_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        select_provider("nope")


def test_configure_observability_is_idempotent() -> None:
    logfire_backend.configure_observability()
    logfire_backend.configure_observability()
    assert logfire_backend._state["configured"] is True
