"""Anonymization-lint tests, single-sourcing the CI/pre-commit check.

Mirrors the seam/skill lint keystone set: a positive gate on the real
``.planning/`` tree, a negative keystone against fixture files (a hit MUST be
detected), and the vacuous-pass guard (an empty root cannot masquerade as clean).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import planning_lint  # noqa: E402


def test_real_planning_tree_is_clean() -> None:
    """The committed .planning/ tree carries no unscrubbed prior-art names."""
    assert planning_lint.main() == 0


@pytest.mark.parametrize(
    "line",
    ["see the angie skills", "the Elastic teardown", "ANGIE-review pattern"],
    ids=["lowercase", "capitalized", "uppercase_prefix"],
)
def test_forbidden_name_is_detected(tmp_path: Path, line: str) -> None:
    """Each unscrubbed prior-art name must yield a hit (negative keystone)."""
    bad = tmp_path / "notes.md"
    bad.write_text(f"clean line\n{line}\n", encoding="utf-8")
    hits = planning_lint.check_file(bad)
    assert hits, f"Expected a violation for {line!r} but check_file returned []."
    assert ":2:" in hits[0]


def test_scrubbed_tokens_pass(tmp_path: Path) -> None:
    """The sanctioned scrubbed tokens (ng/els/c2d/gd) are not violations."""
    ok = tmp_path / "notes.md"
    ok.write_text("the ng family; the els, c2d and gd teardowns\n", encoding="utf-8")
    assert planning_lint.check_file(ok) == []


def test_main_returns_2_on_empty_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``main()`` returns 2 when PLANNING_ROOT has no text files (vacuous guard)."""
    monkeypatch.setattr(planning_lint, "PLANNING_ROOT", tmp_path)
    assert planning_lint.main() == 2


def test_main_returns_1_on_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``main()`` returns 1 when any scanned planning file carries a hit."""
    tmp_path.joinpath("STATE.md").write_text("angie was here\n", encoding="utf-8")
    monkeypatch.setattr(planning_lint, "PLANNING_ROOT", tmp_path)
    assert planning_lint.main() == 1
