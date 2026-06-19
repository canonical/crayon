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

"""Smoke test: the src-layout package and its sub-packages import cleanly."""

import importlib

import dogen


def test_package_and_subpackages_importable() -> None:
    """Every dogen sub-package imports, proving the src-layout is wired."""
    modules = [
        "dogen",
        "dogen.core",
        "dogen.adapters",
        "dogen.adapters.copilot",
        "dogen.cli",
    ]
    for name in modules:
        assert importlib.import_module(name) is not None


def test_version_marker_present() -> None:
    """The package exposes a version string for tooling and provenance."""
    assert isinstance(dogen.__version__, str)
    assert dogen.__version__
