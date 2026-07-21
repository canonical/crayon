"""D-18 skill-invariant lint tests, single-sourcing the CI/pre-commit check.

Mirrors the seam guard's three-file keystone set (``test_seam.py`` positive
gate, ``test_seam_violation_detected.py`` negative keystone,
``test_seam_vacuous_pass.py`` vacuous-pass guard) against fixture skill dirs so
no real ``skills/`` tree is required (that positive gate lands in Plan 04-03/04).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import skill_lint  # noqa: E402


def _make_skill(root: Path, name: str, frontmatter: str) -> Path:
    """Create ``root/<name>/SKILL.md`` with a ``---``-fenced frontmatter block.

    Parameters
    ----------
    root : Path
        The fixture skills root the lint will scan.
    name : str
        The skill directory name (also the expected frontmatter ``name``).
    frontmatter : str
        The YAML body placed between the two ``---`` fences.

    Returns
    -------
    Path
        The created skill directory.
    """
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.joinpath("SKILL.md").write_text(
        f"---\n{frontmatter}\n---\n\nBody.\n", encoding="utf-8"
    )
    return skill_dir


def test_wellformed_write_free_skill_has_no_violations(tmp_path: Path) -> None:
    """A clean write-free skill (name==dir, description, no Write/Edit) passes."""
    skill_dir = _make_skill(
        tmp_path,
        "dogen-plan",
        "name: dogen-plan\ndescription: Plan a documentation unit.\n"
        "allowed-tools: Read, Bash",
    )
    assert skill_lint.check_skill(skill_dir) == []


def test_writer_record_may_carry_write(tmp_path: Path) -> None:
    """A writer in the WRITERS allowlist (dogen-record) may carry Write (D-02)."""
    skill_dir = _make_skill(
        tmp_path,
        "dogen-record",
        "name: dogen-record\ndescription: Record a walk-through draft.\n"
        "allowed-tools: Read, Bash, Write",
    )
    assert skill_lint.check_skill(skill_dir) == []


VIOLATION_CASES = [
    (
        "write_in_non_writer",
        "dogen-plan",
        "name: dogen-plan\ndescription: Plan a unit.\nallowed-tools: Read, Bash, Write",
    ),
    (
        "edit_in_non_writer",
        "dogen-review",
        "name: dogen-review\ndescription: Review a draft.\nallowed-tools: Read, Edit",
    ),
    (
        "arbitrary_non_writer_fail_closed",
        "dogen-explain",
        "name: dogen-explain\ndescription: Explain a unit.\nallowed-tools: Read, Write",
    ),
    (
        "name_mismatch",
        "dogen-plan",
        "name: dogen-planner\ndescription: Plan a unit.\nallowed-tools: Read",
    ),
    (
        "empty_description",
        "dogen-plan",
        "name: dogen-plan\ndescription: '   '\nallowed-tools: Read",
    ),
    (
        "missing_description",
        "dogen-plan",
        "name: dogen-plan\nallowed-tools: Read",
    ),
]


@pytest.mark.parametrize(
    "case,dir_name,frontmatter",
    VIOLATION_CASES,
    ids=[c[0] for c in VIOLATION_CASES],
)
def test_violation_is_detected(
    tmp_path: Path, case: str, dir_name: str, frontmatter: str
) -> None:
    """Each invariant breach must yield at least one violation (negative keystone)."""
    skill_dir = _make_skill(tmp_path, dir_name, frontmatter)
    errs = skill_lint.check_skill(skill_dir)
    assert errs, f"Expected a violation for {case!r} but check_skill returned []."


@pytest.mark.parametrize(
    "allowed_tools",
    ["Read, Bash, Write", "Read Bash Write"],
    ids=["comma_delimited", "space_delimited"],
)
def test_write_detected_under_both_delimiters(
    tmp_path: Path, allowed_tools: str
) -> None:
    """A Write in a non-writer skill is caught under comma OR whitespace delimiters."""
    skill_dir = _make_skill(
        tmp_path,
        "dogen-plan",
        f"name: dogen-plan\ndescription: Plan a unit.\nallowed-tools: {allowed_tools}",
    )
    errs = skill_lint.check_skill(skill_dir)
    assert errs, (
        f"Expected a Write violation with allowed-tools {allowed_tools!r} "
        "(delimiter-agnostic tokenizing, Pitfall 1)."
    )


def test_tools_tokenizes_both_delimiters() -> None:
    """``_tools`` yields the same token set for comma and space delimiters."""
    assert "Write" in skill_lint._tools({"allowed-tools": "Read, Bash, Write"})
    assert "Write" in skill_lint._tools({"allowed-tools": "Read Bash Write"})


def test_main_returns_2_on_empty_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``main()`` returns 2 when SKILLS_ROOT has no SKILL.md files (vacuous guard)."""
    monkeypatch.setattr(skill_lint, "SKILLS_ROOT", tmp_path)
    assert skill_lint.main() == 2


def test_main_returns_0_on_clean_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``main()`` returns 0 when every scanned skill is invariant-clean."""
    _make_skill(
        tmp_path,
        "dogen-plan",
        "name: dogen-plan\ndescription: Plan a unit.\nallowed-tools: Read, Bash",
    )
    _make_skill(
        tmp_path,
        "dogen-write",
        "name: dogen-write\ndescription: Draft a unit.\n"
        "allowed-tools: Read, Bash, Write, Edit",
    )
    monkeypatch.setattr(skill_lint, "SKILLS_ROOT", tmp_path)
    assert skill_lint.main() == 0


def test_main_returns_1_on_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``main()`` returns 1 when any scanned skill breaches an invariant."""
    _make_skill(
        tmp_path,
        "dogen-plan",
        "name: dogen-plan\ndescription: Plan a unit.\nallowed-tools: Read, Write",
    )
    monkeypatch.setattr(skill_lint, "SKILLS_ROOT", tmp_path)
    assert skill_lint.main() == 1
