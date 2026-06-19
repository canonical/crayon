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

"""Seam guardrail as a pytest test, single-sourcing the CI/pre-commit check."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import seam_check  # noqa: E402


def test_no_vendor_imports_outside_adapter() -> None:
    """The core/cli contain no Copilot SDK imports (SEAM-01/02).

    This invokes the exact ``seam_check.main`` that CI and pre-commit run, so
    the test and the build gate share a single source of truth.
    """
    assert seam_check.main() == 0
