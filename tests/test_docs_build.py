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

"""The publishability proof, as a test (SKEL-02).

These tests are the single-source companion to the CI ``sphinx-build -W`` gate:
they assert the MyST config is wired correctly (``myst_parser`` + ``colon_fence``,
Pitfall 6), that the drafted dogfood page is reachable from the toctree (so a
``-W`` build does not fail on an orphan), and — when Sphinx is installed — that a
real warnings-as-errors build of the docs tree succeeds.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _REPO_ROOT / "docs"


def test_conf_enables_myst_and_colon_fence() -> None:
    """conf.py must register MyST and colon_fence, or the build proves nothing."""
    conf = (_DOCS / "conf.py").read_text(encoding="utf-8")
    # Without myst_parser in extensions, .md pages are not parsed as MyST and a
    # -W build "passes" without ever exercising the publishability path.
    assert '"myst_parser"' in conf
    assert "myst_enable_extensions" in conf
    assert '"colon_fence"' in conf


def test_index_toctree_references_drafted_page() -> None:
    """The dogfood page must be in the toctree so -W does not fail on an orphan."""
    index = (_DOCS / "index.md").read_text(encoding="utf-8")
    assert "toctree" in index
    # The dogfood drafted page (D-32) is the publishability proof; it must be
    # reachable from the root toctree.
    assert "cli-reference" in index


def test_drafted_page_is_licensed_via_sidecar() -> None:
    """The drafted page carries CC-BY-SA-4.0 via a sidecar, not inline SPDX (S2)."""
    page = _DOCS / "cli-reference.md"
    sidecar = _DOCS / "cli-reference.md.license"
    assert page.exists()
    assert sidecar.exists()
    # No inline SPDX header in the published prose (it would pollute the page and
    # be misparsed by reuse); the license lives in the sidecar.
    assert "SPDX-License-Identifier" not in page.read_text(encoding="utf-8")
    assert "CC-BY-SA-4.0" in sidecar.read_text(encoding="utf-8")


@pytest.mark.skipif(
    shutil.which("sphinx-build") is None,
    reason="sphinx-build not installed (docs extra); CI runs it with --extra docs",
)
def test_sphinx_build_warnings_as_errors(tmp_path: Path) -> None:
    """A real -W build of the docs tree must succeed (the SKEL-02 proof)."""
    out = tmp_path / "_build"
    result = subprocess.run(  # noqa: S603
        [
            "sphinx-build",
            "-W",
            "-b",
            "html",
            str(_DOCS),
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
