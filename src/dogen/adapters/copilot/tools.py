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

"""The bounded read-only toolset that constrains the drafting agent (D-28/SKEL-04).

This module is the security boundary for the Copilot adapter. The agent is given
a deliberately minimal **allowlist** of read-only lookup tools and an explicit
**denylist** of every write/exec/network tool, so injected instructions in the
source content it reads cannot make it act outside drafting (threat T-02.3-01/02).

The exact built-in tool names were confirmed against the authenticated Copilot
CLI runtime (``1.0.64-0``, protocol 3) by a live probe before this allowlist was
locked — resolving Assumption A1 (RESEARCH Open Question 1):

* **Read-only (allowlist):** ``grep``, ``glob``, ``view`` — source/repo read tools
  only. ``web_fetch`` is *excluded* because it is network access (denied by D-28).
* **Write/exec/network (denylist):** ``bash``, ``edit``, ``create``, ``stop_bash``,
  ``sql``, ``task``, ``skill``, ``web_fetch`` — the confirmed mutating/host-reaching
  tools. (The plan text assumed ``str_replace_editor``; the live probe shows the
  real registered file-edit tool is ``edit``.)

Names are **source-qualified** via :meth:`ToolSet.add_builtin`, which emits
``builtin:<name>`` filter strings; passing bare strings raises (RESEARCH Pitfall 1).
The allowlist is the primary control (only ``grep``/``glob``/``view`` are even
available); the denylist is belt-and-braces defense-in-depth.
"""

from copilot import ToolSet

# Read-only lookup tools the agent is permitted to use (D-28 allowlist).
_READONLY_NAMES: list[str] = ["grep", "glob", "view"]

# Write/exec/network tools the agent is explicitly denied (D-28 denylist).
_DENY_NAMES: list[str] = [
    "bash",
    "edit",
    "create",
    "stop_bash",
    "sql",
    "task",
    "skill",
    "web_fetch",
]

# The primary security control: only these read-only tools are available.
READONLY: ToolSet = ToolSet().add_builtin(_READONLY_NAMES)

# Belt-and-braces: deny every confirmed write/exec/network tool by name.
DENY: ToolSet = ToolSet().add_builtin(_DENY_NAMES)
