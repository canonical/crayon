# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

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

    content: str
    model: str | None
    output_tokens: int | None


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
        _FakeAssistantData(content="# Title\n\nbody", model="gpt-5", output_tokens=42)
    )
    result = to_draft_result(evt, run_id="abc123")

    assert isinstance(result, DraftResult)
    assert result.text == "# Title\n\nbody"
    assert result.model == "gpt-5"
    assert result.output_tokens == 42
    assert result.run_id == "abc123"


def test_to_draft_result_coerces_missing_model_and_tokens() -> None:
    evt = _event(_FakeAssistantData(content="draft", model=None, output_tokens=None))
    result = to_draft_result(evt, run_id="r")

    # None must never leak into the domain record; coerce to safe defaults.
    assert result.model == "unknown"
    assert result.output_tokens == 0
    assert result.text == "draft"


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
