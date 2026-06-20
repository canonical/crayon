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

"""The provider seam: the sole sanctioned GitHub Copilot SDK import site.

This package is the single location where ``copilot`` / ``github_copilot_sdk``
may be imported (SEAM-01); the AST seam guardrail and the import-linter forbidden
contract exempt this subtree alone.

Phase 1 left the boundary intentionally empty (D-08, deferred dependency); that
dependency has now landed. The real :class:`CopilotDraftingProvider` implements
the same ``core.ports.DraftingProvider`` port the deterministic mock proved
(SEAM-03), driving a bounded read-only Copilot session and converting a
backend-unavailable runtime into a handled :class:`BackendUnavailableError`
(SKEL-05/D-27). The CI loop still runs on ``--provider mock``; the real SDK is
exercised only by the manual local smoke harness (D-24).
"""

from dogen.adapters.copilot.provider import (
    BackendUnavailableError,
    CopilotDraftingProvider,
)

__all__ = ["BackendUnavailableError", "CopilotDraftingProvider"]
