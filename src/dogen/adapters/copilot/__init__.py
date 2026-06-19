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
may be imported (SEAM-01); the AST seam guardrail exempts this subtree alone.

In Phase 1 the boundary is intentionally empty: it takes no real
``github-copilot-sdk`` dependency (D-08). It exists as the designated shape so
that the adapter implementation can land in a later phase without disturbing
the core or the seam invariant.
"""
