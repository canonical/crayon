"""FND-01 regression: seam_check.main() returns 2 when zero .py files are scanned."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import seam_check  # noqa: E402


def test_seam_check_returns_2_on_empty_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """seam_check.main() must return 2 when PKG_ROOT contains no .py files (FND-01).

    The vacuous-pass guard prevents a misconfigured scan root from silently
    passing: if scanned == 0, main() returns 2 instead of 0, so a broken path
    cannot masquerade as a clean seam.
    """
    monkeypatch.setattr(seam_check, "PKG_ROOT", tmp_path)
    monkeypatch.setattr(seam_check, "ADAPTER_DIR", tmp_path / "adapters" / "copilot")
    assert seam_check.main() == 2
