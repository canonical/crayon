"""Anti-corruption mapping tests: SDK event -> DraftResult, no SDK type in core.

These exercise ``adapters/copilot/mapping.to_draft_result`` with lightweight
fakes — no live SDK call — proving the vendor's ``assistant.message`` shape is
translated into the pure-domain ``DraftResult`` at the seam (Pitfall 4). Bounded
read-only ``tools.py`` constants are asserted to be source-qualified ToolSets.
"""

from dataclasses import dataclass
from typing import cast

import pytest
from copilot import SessionEvent, ToolSet

from dogen.adapters.copilot.mapping import to_draft_result
from dogen.adapters.copilot.tools import DENY, READONLY
from dogen.core.models import DraftResult


@dataclass
class _FakeAssistantData:
    """A minimal stand-in for ``AssistantMessageData`` (no SDK construction)."""

    content: str | None
    model: str | None
    output_tokens: int | None
    model_version: str | None = None


@dataclass
class _FakeEvent:
    """A minimal stand-in for ``SessionEvent`` carrying ``.data``."""

    data: _FakeAssistantData


def _event(data: _FakeAssistantData) -> SessionEvent:
    # The mapping reads only ``.data.content/.model/.output_tokens`` by attribute;
    # the fake is structurally sufficient. Cast keeps the strict type checker happy
    # without constructing a full SDK event in a unit test.
    return cast(SessionEvent, _FakeEvent(data))


def test_to_draft_result_maps_content_model_tokens_and_run_id() -> None:
    evt = _event(
        _FakeAssistantData(
            content="# Title\n\nbody",
            model="gpt-5",
            output_tokens=42,
            model_version="gpt-5-2026-01",
        )
    )
    result = to_draft_result(evt, run_id="abc123")

    assert isinstance(result, DraftResult)
    assert result.text == "# Title\n\nbody"
    assert result.model == "gpt-5"
    assert result.model_version == "gpt-5-2026-01"
    assert result.output_tokens == 42
    assert result.run_id == "abc123"


def test_to_draft_result_coerces_missing_model_and_tokens() -> None:
    evt = _event(_FakeAssistantData(content="draft", model=None, output_tokens=None))
    result = to_draft_result(evt, run_id="r")

    # None must never leak into the domain record; coerce to safe defaults.
    assert result.model == "unknown"
    # An absent version must record a distinct sentinel, never the model name (WR-03).
    assert result.model_version == "unknown"
    assert result.output_tokens == 0
    assert result.text == "draft"


def test_to_draft_result_coerces_none_content() -> None:
    # WR-05: a truncated/unfinalised stream can deliver content=None. That must
    # degrade to an empty string, not raise a Pydantic ValidationError on the
    # str-typed DraftResult.text (an uncaught crash the seam must never surface).
    evt = _event(_FakeAssistantData(content=None, model="gpt-5", output_tokens=3))
    result = to_draft_result(evt, run_id="r")

    assert isinstance(result, DraftResult)
    assert result.text == ""
    assert result.model == "gpt-5"


@pytest.mark.parametrize(
    ("constant", "expected"),
    [
        (READONLY, {"grep", "glob", "view"}),
        (
            DENY,
            {
                "bash",
                "edit",
                "create",
                "stop_bash",
                "sql",
                "task",
                "skill",
                "web_fetch",
            },
        ),
    ],
)
def test_toolsets_are_source_qualified_builtins(
    constant: ToolSet, expected: set[str]
) -> None:
    # Both constants must be ToolSet instances built via add_builtin (Pitfall 1):
    # bare strings would raise, and source-qualification emits ``builtin:<name>``.
    assert isinstance(constant, ToolSet)
    filters = set(constant.to_list())
    assert filters == {f"builtin:{name}" for name in expected}
