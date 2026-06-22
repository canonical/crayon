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

"""Observed-provenance tests for the Copilot adapter (no live SDK, D-24).

Two layers, both driven by a fake SDK so they run in CI (D-06, criterion 4):

* The pure-helper layer pins
  :func:`dogen.adapters.copilot.mapping.tool_events_to_provenance` — scripted
  ``TOOL_EXECUTION_START`` events translate to ``(context_origins, tools_used)``
  with first-seen de-dup and omit-on-doubt guards (PROV-01/02, D-02/D-03/D-05).
* The end-to-end layer drives the real
  :class:`~dogen.adapters.copilot.provider.CopilotDraftingProvider` against the
  shared ``_StubSession`` (its ``get_events`` returns the scripted history) and
  asserts the populated lists reach the ``DraftResult`` and the recorded
  ``Generation`` through the orchestrator's verbatim copy.

The shared ``conftest`` stays SDK-free at collection (WR-02): the only ``copilot``
imports are function-local, inside the event builders, mirroring ``_assistant_event``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

import pytest

from dogen.adapters.copilot.mapping import tool_events_to_provenance
from dogen.adapters.copilot.provider import CopilotDraftingProvider

from .conftest import _draft

if TYPE_CHECKING:
    from copilot import SessionEvent


def _tool_start(tool_name: str, arguments: dict | None) -> SessionEvent:
    """Build a scripted ``TOOL_EXECUTION_START`` event for the given tool.

    The function-local ``copilot`` import keeps this module's collection
    SDK-free (WR-02); only running a builder pulls ``copilot`` into
    ``sys.modules``.
    """
    from copilot import SessionEvent, SessionEventType  # noqa: PLC0415
    from copilot.session_events import ToolExecutionStartData  # noqa: PLC0415

    event = SessionEvent(
        data=ToolExecutionStartData(
            tool_call_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
        ),
        id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        type=SessionEventType.TOOL_EXECUTION_START,
    )
    return cast("SessionEvent", event)


def _tool_complete(tool_name: str) -> SessionEvent:
    """Build a scripted ``TOOL_EXECUTION_COMPLETE`` event (no name/args ride it).

    Used to prove the helper counts START events only — a COMPLETE in the
    history contributes nothing (RESEARCH Pitfall 1).
    """
    from copilot import SessionEvent, SessionEventType  # noqa: PLC0415
    from copilot.session_events import ToolExecutionCompleteData  # noqa: PLC0415

    event = SessionEvent(
        data=ToolExecutionCompleteData(
            tool_call_id=str(uuid.uuid4()),
            success=True,
        ),
        id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
    )
    return cast("SessionEvent", event)


# --- Pure-helper translation tests (PROV-01/02, D-02/D-03/D-05) ---


def test_view_path_becomes_origin_and_tool() -> None:
    # PROV-01/02: a view read records both the read path (origin) and the
    # builtin:view identifier.
    origins, tools = tool_events_to_provenance(
        [_tool_start("view", {"path": "README.md"})]
    )
    assert origins == ["README.md"]
    assert tools == ["builtin:view"]


def test_duplicate_view_is_deduped() -> None:
    # D-02/D-03: first-seen de-dup — a repeated view of the same path appears once.
    origins, tools = tool_events_to_provenance(
        [
            _tool_start("view", {"path": "README.md"}),
            _tool_start("view", {"path": "README.md"}),
        ]
    )
    assert origins == ["README.md"]
    assert tools == ["builtin:view"]


def test_grep_adds_tool_but_no_origin() -> None:
    # grep is a discovery tool — its pattern is not a guaranteed content read
    # (omit-on-doubt): record the tool, never a context origin.
    origins, tools = tool_events_to_provenance(
        [_tool_start("grep", {"pattern": "TODO"})]
    )
    assert origins == []
    assert tools == ["builtin:grep"]


def test_glob_adds_tool_but_no_origin() -> None:
    origins, tools = tool_events_to_provenance(
        [_tool_start("glob", {"pattern": "**/*.md"})]
    )
    assert origins == []
    assert tools == ["builtin:glob"]


def test_first_seen_ordering_across_mixed_sequence() -> None:
    # The RESEARCH-verified mixed sequence: first-seen order, view's path the
    # only origin, duplicate view de-duped.
    origins, tools = tool_events_to_provenance(
        [
            _tool_start("view", {"path": "README.md"}),
            _tool_start("grep", {"pattern": "TODO"}),
            _tool_start("view", {"path": "README.md"}),
            _tool_start("glob", {"pattern": "**/*.md"}),
        ]
    )
    assert origins == ["README.md"]
    assert tools == ["builtin:view", "builtin:grep", "builtin:glob"]


def test_empty_events_is_honest_empty() -> None:
    # D-05/BL-01: no observed events → both lists honestly empty.
    assert tool_events_to_provenance([]) == ([], [])


def test_malformed_arguments_none_does_not_crash() -> None:
    # T-04-01 / Pitfall 2: a view event whose arguments is None must not raise
    # and must record no origin (omit-on-doubt, V5).
    origins, tools = tool_events_to_provenance([_tool_start("view", None)])
    assert origins == []
    assert tools == ["builtin:view"]


def test_complete_event_contributes_nothing() -> None:
    # Pitfall 1: only TOOL_EXECUTION_START is counted — a COMPLETE in the
    # history carries no tool_name/arguments and must contribute nothing.
    origins, tools = tool_events_to_provenance(
        [_tool_start("view", {"path": "README.md"}), _tool_complete("view")]
    )
    assert origins == ["README.md"]
    assert tools == ["builtin:view"]


# --- Fake-SDK end-to-end provenance tests (criterion 4, D-06) ---


@pytest.mark.asyncio
async def test_draft_populates_provenance_from_observed_events(
    install_stub_client,
) -> None:
    # Criterion 4: a scripted get_events() history drives the real provider
    # through _run_draft and the populated lists reach the DraftResult.
    install_stub_client(
        events=[
            _tool_start("view", {"path": "README.md"}),
            _tool_start("grep", {"pattern": "TODO"}),
        ]
    )
    result = await _draft(CopilotDraftingProvider())
    assert result.context_origins == ["README.md"]
    assert result.tools_used == ["builtin:view", "builtin:grep"]


@pytest.mark.asyncio
async def test_draft_honest_empty_when_no_events(install_stub_client) -> None:
    # D-05/BL-01: no observed events → both lists honestly empty end-to-end.
    install_stub_client()
    result = await _draft(CopilotDraftingProvider())
    assert result.context_origins == []
    assert result.tools_used == []
