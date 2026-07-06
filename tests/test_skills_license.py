"""LIC-02 regression: skills/LICENSE is Apache-2.0 and is NOT bundled in the wheel."""

import shutil
import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_LICENSE = REPO_ROOT / "skills" / "LICENSE"


def test_skills_license_is_apache(tmp_path: Path) -> None:
    """skills/LICENSE must exist and declare Apache License Version 2.0.

    LIC-02 first half.
    """
    assert SKILLS_LICENSE.exists(), (
        f"skills/LICENSE not found at {SKILLS_LICENSE}. "
        "LIC-02 requires a separate Apache-2.0 license file for the skill family."
    )
    header = SKILLS_LICENSE.read_text(encoding="utf-8")[:1000]
    assert "Apache License" in header, (
        "skills/LICENSE does not contain 'Apache License' in the first 1000 bytes."
    )
    assert "Version 2.0" in header, (
        "skills/LICENSE does not contain 'Version 2.0' in the first 1000 bytes."
    )


def test_skills_license_absent_from_wheel(tmp_path: Path) -> None:
    """Built wheel must NOT bundle skills/LICENSE (Apache-2.0).

    LIC-02 second half: pyproject.toml sets license-files = ["LICENSE"] (root only).
    Hatchling/PEP-639 must exclude skills/LICENSE from the wheel's
    dist-info/licenses/ subtree.
    """
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
        # Find all license entries under *.dist-info/licenses/
        license_entries = [n for n in zf.namelist() if "dist-info/licenses/" in n]

        # The root LGPL LICENSE must be bundled
        assert license_entries, (
            f"No dist-info/licenses/ entries found in {wheel.name}. "
            "Expected the root LGPL-3.0-only LICENSE to be bundled."
        )

        # No bundled license file may contain Apache License text
        apache_bundled = []
        for entry in license_entries:
            content = zf.read(entry).decode("utf-8", errors="replace")
            if "Apache License" in content:
                apache_bundled.append(entry)

    assert not apache_bundled, (
        f"skills/LICENSE (Apache-2.0) was incorrectly bundled in {wheel.name}.\n"
        f"Offending entries: {apache_bundled}\n"
        "pyproject.toml license-files = ['LICENSE'] should exclude skills/LICENSE."
    )
