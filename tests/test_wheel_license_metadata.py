"""LIC-01 regression: built wheel METADATA carries License-Expression: LGPL-3.0-only."""

import shutil
import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contains_license_expression(tmp_path: Path) -> None:
    """Built wheel METADATA must carry License-Expression: LGPL-3.0-only (LIC-01)."""
    uv = shutil.which("uv")
    assert uv is not None, (
        "uv is not on PATH — cannot build wheel. Install uv to satisfy LIC-01 check."
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
    assert "License-Expression: LGPL-3.0-only" in metadata, (
        "License-Expression: LGPL-3.0-only not found in wheel METADATA.\n"
        f"Relevant lines:\n{license_lines}"
    )
