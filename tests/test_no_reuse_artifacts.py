"""LIC-01 regression: no residual REUSE/SPDX markers in the project's tracked source.

This closes the half of LIC-01 that no lifted test covers (RESEARCH Wave 0 gap):
the total REUSE strip (D-01) must leave zero per-file SPDX license-identifier or
file-copyright markers in dogen's OWN tracked source. It enumerates only
``git ls-files`` output (so the gitignored ``prior-research/`` prior-art tree —
which is full of GPL/REUSE markers — is never scanned) and asserts no marker
survives.

SELF-MATCH GUARD: this file searches for the very markers it forbids, so each
needle is assembled at runtime by concatenation. That keeps this module's own
source free of the contiguous marker token; the test's path is also skipped
defensively.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Built by concatenation so this file never contains the contiguous marker token.
_LICENSE_MARKER = "SPDX-License-" + "Identifier"
_COPYRIGHT_MARKER = "SPDX-File" + "CopyrightText"
FORBIDDEN_MARKERS = (_LICENSE_MARKER, _COPYRIGHT_MARKER)

# Source kinds where a stray SPDX/REUSE header would plausibly survive a strip.
SCANNED_SUFFIXES = {".py", ".toml", ".yaml", ".yml", ".cfg", ".ini"}

SELF_PATH = Path(__file__).resolve()


def _tracked_source_files() -> list[Path]:
    """Return tracked source files of the scanned kinds, excluding this test.

    Returns
    -------
    list of Path
        Absolute paths from ``git ls-files`` filtered to
        :data:`SCANNED_SUFFIXES`, with this test module removed (it carries the
        forbidden markers as split-needle data, not as real headers).
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files: list[Path] = []
    for rel in out.split("\0"):
        if not rel:
            continue
        path = (REPO_ROOT / rel).resolve()
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        if path == SELF_PATH:
            continue
        files.append(path)
    return files


def test_no_residual_reuse_markers() -> None:
    """No tracked source file may contain a REUSE/SPDX marker (D-01 / LIC-01)."""
    offenders: list[str] = []
    for path in _tracked_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}: contains {marker}")
    assert not offenders, "Residual REUSE/SPDX markers found in tracked source:\n" + (
        "\n".join(offenders)
    )
