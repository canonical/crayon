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
