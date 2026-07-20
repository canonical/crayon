"""RED-first: SK-05 border normalization across the four dogen skills.

Round-3 finding H was border drift: dogen-plan carried no ``<output_specification>``
at all, and the open/close shapes each leg improvised diverged (bare vs backticked
referrals, no state check, inconsistent close blocks). SK-05 normalizes the family
to ONE shared border shape:

- **OPEN** — every skill confirms the target unit and performs a state check (the
  unit's current lifecycle state) before the main workflow.
- **CLOSE** — every skill ends with an output block carrying the ``git: committed``
  relay line(s) and the frozen ``Next: /dogen-<skill> — <imperative>.`` referral.

dogen-write's ``<objective>`` open and ``<output_specification>`` close are the
canonical shape the other three are normalized TO. This guard pins the shared shape
so it cannot silently re-drift (round 3 proved re-wording drifts); dogen-record
(the fourth family skill) is guarded here alongside plan/write/review.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS = _REPO_ROOT / "skills"
_PLAN = _SKILLS / "dogen-plan" / "SKILL.md"
_WRITE = _SKILLS / "dogen-write" / "SKILL.md"
_REVIEW = _SKILLS / "dogen-review" / "SKILL.md"
_RECORD = _SKILLS / "dogen-record" / "SKILL.md"
_ALL_FOUR = (_PLAN, _WRITE, _REVIEW, _RECORD)


def _text(path: Path) -> str:
    """Return the UTF-8 text of ``path``."""
    return path.read_text(encoding="utf-8")


def _output_spec(path: Path) -> str:
    """Return the ``<output_specification>`` block (the CLOSE border) of a skill."""
    text = _text(path)
    start = text.index("<output_specification>")
    end = text.index("</output_specification>", start)
    return text[start:end]


# ---- Task 1: dogen-plan gains an <output_specification> ---------------------


def test_dogen_plan_has_output_specification() -> None:
    """dogen-plan was the only skill without an ``<output_specification>`` (SK-05)."""
    text = _text(_PLAN)
    assert "<output_specification>" in text and "</output_specification>" in text, (
        "skills/dogen-plan/SKILL.md must gain exactly one <output_specification> "
        "block (SK-05) — it was the only skill without one."
    )


def test_dogen_plan_output_spec_carries_referral_and_commit() -> None:
    """dogen-plan's close block quotes the git relay + the frozen referral (SK-05)."""
    spec = _output_spec(_PLAN).lower()
    assert "next: /dogen-" in spec, (
        "dogen-plan's <output_specification> close must carry the frozen "
        "`Next: /dogen-<skill>` referral line (SK-05, README routing table)."
    )
    assert "git: committed" in spec, (
        "dogen-plan's <output_specification> close must quote the `git: committed` "
        "relay produced by the declaration ceremony (SK-05)."
    )


# ---- Task 2: cross-skill open/close normalization --------------------------


def _open_region(path: Path) -> str:
    """Return the OPEN border — everything before ``<pipeline>``.

    The opening border is the ``<objective>`` + ``<quick_start>`` region where each
    skill confirms the target unit and performs its state check before the workflow.
    """
    text = _text(path)
    return text[: text.index("<pipeline>")]


def test_all_closes_carry_frozen_referral_and_commit() -> None:
    """All four CLOSE borders quote the git relay + the frozen referral (SK-05)."""
    for path in _ALL_FOUR:
        spec = _output_spec(path).lower()
        assert "next: /dogen-" in spec, (
            f"{path.parent.name}'s <output_specification> close must carry the "
            "frozen `Next: /dogen-<skill>` referral line (SK-05)."
        )
        assert "git: committed" in spec, (
            f"{path.parent.name}'s <output_specification> close must quote the "
            "`git: committed` relay (SK-05)."
        )


def test_all_opens_confirm_unit_and_state_check() -> None:
    """All four OPEN borders confirm the target unit + a state check (SK-05)."""
    for path in _ALL_FOUR:
        opening = _open_region(path).lower()
        assert "confirm the target unit" in opening, (
            f"{path.parent.name}'s open must confirm the target unit — the shared "
            "normalized OPEN shape (SK-05)."
        )
        assert "check its current state" in opening, (
            f"{path.parent.name}'s open must perform a state check (the unit's "
            "current lifecycle state) — the shared normalized OPEN shape (SK-05)."
        )


# ---- Body-cleanliness guard: no leaked authoring-wrapper tags (CR-01) -------

# The four Write-tool-call XML wrappers (content-wrapper + invoke-wrapper, opener
# and closer). None of these is skill markup — they are the shipped bytes of the
# authoring harness's tool call, and must never appear in an auto-loaded skill file.
_LEAKED_WRAPPER_TAGS = ("</content>", "</invoke>", "<content>", "<invoke>")


def _all_skill_markdown_files() -> list[Path]:
    """Every auto-loaded skill markdown: each SKILL.md + all its references/*.md.

    The four SKILL.md files are the canonical ``_ALL_FOUR`` anchors; references are
    glob-derived per skill (not hard-coded) so a newly added reference is covered
    automatically.
    """
    files: list[Path] = []
    for skill_md in _ALL_FOUR:
        files.append(skill_md)
        files.extend(sorted((skill_md.parent / "references").glob("*.md")))
    return files


def test_no_authoring_wrapper_tags_leaked() -> None:
    """No shipped skill file may carry a leaked authoring-wrapper tag (CR-01).

    ``test_skill_borders`` above uses ``.index()`` and is structurally blind to
    trailing junk after the matched border blocks. This guard reads each file's
    full body and negative-asserts every wrapper literal, so the leak class that
    shipped in all four dogen-record files (``</content>`` / ``</invoke>`` after
    the true final content) cannot re-ship undetected — in SKILL.md OR any
    references/*.md of any of the four skills.
    """
    for path in _all_skill_markdown_files():
        text = _text(path)
        for stray in _LEAKED_WRAPPER_TAGS:
            assert stray not in text, (
                f"{path.parent.name}/{path.name}: leaked authoring-wrapper tag "
                f"{stray!r} — delete the stray wrapper line(s); a SKILL.md ends at "
                "its </self_healing> block and a reference ends at its last prose "
                "sentence, with nothing after it (CR-01)."
            )
