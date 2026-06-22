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

"""V4 security regression guard: the ``READONLY`` / ``DENY`` toolset is unchanged.

Plan 03-02 wires ``PermissionHandler.approve_all`` into the Copilot session so
the non-interactive live path can auto-approve tool calls. That auto-approval is
only safe while the available toolset stays the bounded read-only allowlist
(``grep`` / ``glob`` / ``view``) and the explicit denylist of every write / exec /
network tool. These tests pin both source-qualified ``builtin:<name>`` sets so a
future edit to :mod:`dogen.adapters.copilot.tools` cannot quietly broaden what
``approve_all`` is allowed to approve (V4; RESEARCH Security Domain). ``tools.py``
itself is NOT modified in Phase 3 — this guard locks it.

The assertion shape is copied from
``tests/test_copilot_mapping.py::test_toolsets_are_source_qualified_builtins``.
"""

from copilot import ToolSet

from dogen.adapters.copilot.tools import DENY, READONLY


def test_readonly_set_unchanged() -> None:
    """Pin the read-only allowlist to exactly ``grep`` / ``glob`` / ``view``.

    Asserts ``READONLY`` is a ``ToolSet`` whose source-qualified filter strings
    are precisely the three read-only lookup tools — no broadening.
    """
    assert isinstance(READONLY, ToolSet)
    expected = {"grep", "glob", "view"}
    assert set(READONLY.to_list()) == {f"builtin:{name}" for name in expected}


def test_deny_set_unchanged() -> None:
    """Pin the denylist to its exact eight write / exec / network tool names.

    Asserts ``DENY`` is a ``ToolSet`` whose source-qualified filter strings are
    precisely the confirmed mutating / host-reaching tools — no narrowing that
    would let a denied tool slip through.
    """
    assert isinstance(DENY, ToolSet)
    expected = {
        "bash",
        "edit",
        "create",
        "stop_bash",
        "sql",
        "task",
        "skill",
        "web_fetch",
    }
    assert set(DENY.to_list()) == {f"builtin:{name}" for name in expected}
