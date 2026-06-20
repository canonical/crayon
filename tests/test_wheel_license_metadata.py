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

"""LIC-02 regression: built wheel METADATA carries License-Expression: GPL-3.0-only."""

import shutil
import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contains_license_expression(tmp_path: Path) -> None:
    """The built wheel METADATA must carry License-Expression: GPL-3.0-only (LIC-02)."""
    uv = shutil.which("uv")
    assert uv is not None, (
        "uv is not on PATH — cannot build wheel. Install uv to satisfy LIC-02 check."
    )

    result = subprocess.run(  # noqa: PLW1510
        [uv, "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"uv build failed (exit {result.returncode}).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    wheels = list(tmp_path.glob("*.whl"))
    assert wheels, f"No .whl file found in {tmp_path} after uv build."

    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as zf:
        metadata_names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        assert metadata_names, f"No METADATA entry found inside {wheel.name}."
        metadata = zf.read(metadata_names[0]).decode("utf-8")

    license_lines = "\n".join(
        line for line in metadata.splitlines() if "icense" in line
    )
    assert "License-Expression: GPL-3.0-only" in metadata, (
        "License-Expression: GPL-3.0-only not found in wheel METADATA.\n"
        f"Relevant lines:\n{license_lines}"
    )
