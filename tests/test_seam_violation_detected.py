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

"""SEAM-02 failure-path: seam_check.find_violations detects all banned import forms."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import seam_check  # noqa: E402

VIOLATION_CASES = [
    ("import_copilot", "import copilot\n"),
    ("import_copilot_aliased", "import copilot as c\n"),
    ("from_copilot_submodule", "from copilot.session import PermissionHandler\n"),
    ("import_github_copilot_sdk", "import github_copilot_sdk\n"),
    (
        "importlib_import_module_copilot",
        "import importlib\nimportlib.import_module('copilot')\n",
    ),
]


@pytest.mark.parametrize(
    "name,source", VIOLATION_CASES, ids=[c[0] for c in VIOLATION_CASES]
)
def test_banned_import_is_detected(tmp_path: Path, name: str, source: str) -> None:
    """Each banned import form must produce at least one violation hit (SEAM-02)."""
    victim = tmp_path / f"{name}.py"
    victim.write_text(source, encoding="utf-8")
    hits = seam_check.find_violations(victim)
    assert hits, (
        f"Expected a violation for {name!r} but find_violations returned []."
        f" Source:\n{source}"
    )


def test_clean_file_returns_no_violations(tmp_path: Path) -> None:
    """A file with no banned imports must return [] (negative control)."""
    clean = tmp_path / "clean.py"
    clean.write_text("import os\nfrom pathlib import Path\n", encoding="utf-8")
    hits = seam_check.find_violations(clean)
    assert hits == [], f"Expected no violations for a clean file but got: {hits}"
