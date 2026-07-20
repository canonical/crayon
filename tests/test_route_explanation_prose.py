"""Prose pins for dogen-write's explanation drafting stance (Phase 15, EXPL-04).

Plan 15-02 gives dogen-write an explanation drafting stance: a new lazy-loaded
``references/explanation-stance.md`` loaded only when the unit's declared
direction is explanation (EXPL-04, D-07), plus two skill-prose guards wired into
``dogen-write/SKILL.md`` — the D-10 empty-steering open-ceremony stop and the
D-09 driver passenger-only note. Four invariants are pinned here the same way
``test_route_dogen_plan_prose.py`` pins dogen-plan's routing: load-bearing
literals defined ONCE as module constants, asserted with POSITIVE presence
checks, and the reference-side files SHA byte-frozen.

- **The stance exists with its frozen load-line (EXPL-04, D-07).** The new file's
  first body line follows the ``references/`` load-line convention.
- **The stance is understanding-oriented (D-08).** Its body names the
  rationale/context/trade-offs/connections register and the recorded-intent
  primary source — positive-presence markers.
- **The two skill guards are present (D-09, D-10).** The D-10 empty-steering
  stop and the D-09 driver passenger-only note are in dogen-write's SKILL.md.
- **The reference path stays byte-identical (D-07, regression).**
  ``writing-standards.md`` and ``provider-branch.md`` are SHA-pinned; a
  single-byte drift fails the guard.

Assertions are deliberately POSITIVE — this module adds no file-wide absence
gate. The reference route legitimately keeps its own register untouched.
"""

import hashlib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOGEN_WRITE = _REPO_ROOT / "skills" / "dogen-write" / "SKILL.md"
_REFERENCES = _REPO_ROOT / "skills" / "dogen-write" / "references"
_EXPLANATION_STANCE = _REFERENCES / "explanation-stance.md"
_WRITING_STANDARDS = _REFERENCES / "writing-standards.md"
_PROVIDER_BRANCH = _REFERENCES / "provider-branch.md"

# The frozen references/ load-line convention (skills/README.md). Every lazy-load
# reference file opens with `Load this file at workflow step N (Name).` — the
# stance file's line 1 startswith this prefix and endswith a period.
STANCE_LOAD_LINE_PREFIX = "Load this file at workflow step "

# The understanding-oriented register the stance body carries (D-08). Every entry
# must be present verbatim — these name the explanation register (rationale,
# context, trade-offs, connections — "why things are the way they are") and the
# recorded-intent primary source, authored to match Task 2.
UNDERSTANDING_MARKERS = (
    "rationale",
    "trade-offs",
    "connections",
    "why things are the way they are",
    "recorded intent",
)

# The D-10 empty-steering open-ceremony stop (positive-presence). dogen-write's
# SKILL.md carries this verbatim — an explanation unit reaching the open ceremony
# with an empty steering stream STOPS and routes back to dogen-plan's intent walk.
MISSING_STEERING_GUARD_MARKER = "explanation unit whose steering stream is empty"

# The D-09 driver honest note (positive-presence). The driver branch carries this
# verbatim — a driver provider has no explanation stance variant, an honest note
# rather than a new prompt path.
PASSENGER_ONLY_MARKER = "no explanation stance variant"

# writing-standards.md is byte-frozen this phase (D-07 regression). This is its
# current SHA-256; the test fails if a single byte changes. A legitimate future
# edit must CONSCIOUSLY update this pin.
WRITING_STANDARDS_SHA256 = (
    "39099d46a437b1150fafd265f99111942e42334454135ea4889c6e0d59242a61"
)

# provider-branch.md is byte-frozen this phase (D-07 regression) — the reference
# stance contract must NOT be applied to explanation. Same conscious-repin rule.
PROVIDER_BRANCH_SHA256 = (
    "549f9f24a8d541846c6d122b36cf56d7e6356cc48d5bfb05d030b181cd600ecb"
)


def test_explanation_stance_exists_with_load_line() -> None:
    assert _EXPLANATION_STANCE.is_file(), (
        "skills/dogen-write/references/explanation-stance.md is missing "
        "(EXPL-04, D-07). dogen-write loads it on the explanation direction."
    )
    first_line = _EXPLANATION_STANCE.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith(STANCE_LOAD_LINE_PREFIX) and first_line.endswith(
        "."
    ), (
        "explanation-stance.md's first body line must follow the frozen "
        f"references/ convention — startswith {STANCE_LOAD_LINE_PREFIX!r} and "
        f"endswith '.'; found {first_line!r}."
    )


def test_explanation_stance_is_understanding_oriented() -> None:
    body = _EXPLANATION_STANCE.read_text(encoding="utf-8")
    missing = [marker for marker in UNDERSTANDING_MARKERS if marker not in body]
    assert not missing, (
        "explanation-stance.md is missing understanding-oriented marker(s) "
        f"{missing!r} (D-08). The stance must name the rationale/context/"
        "trade-offs/connections register and the recorded-intent primary source."
    )


def test_dogen_write_carries_missing_steering_guard() -> None:
    prose = _DOGEN_WRITE.read_text(encoding="utf-8")
    assert MISSING_STEERING_GUARD_MARKER in prose, (
        "skills/dogen-write/SKILL.md is missing the D-10 empty-steering guard "
        f"marker {MISSING_STEERING_GUARD_MARKER!r}. The open ceremony must STOP "
        "and route an unsteered explanation unit back to dogen-plan's walk."
    )


def test_dogen_write_carries_passenger_only_note() -> None:
    prose = _DOGEN_WRITE.read_text(encoding="utf-8")
    assert PASSENGER_ONLY_MARKER in prose, (
        "skills/dogen-write/SKILL.md is missing the D-09 driver honest note "
        f"marker {PASSENGER_ONLY_MARKER!r}. The driver branch must state the "
        "explanation stance is passenger-only this phase — no new prompt path."
    )


def test_writing_standards_is_byte_frozen() -> None:
    # D-07 regression: writing-standards.md is byte-unchanged this phase. If this
    # fails after a deliberate edit, update WRITING_STANDARDS_SHA256 consciously.
    digest = hashlib.sha256(_WRITING_STANDARDS.read_bytes()).hexdigest()
    assert digest == WRITING_STANDARDS_SHA256, (
        "skills/dogen-write/references/writing-standards.md changed — it is "
        "byte-frozen this phase (D-07 regression). If the edit is deliberate, "
        f"update WRITING_STANDARDS_SHA256 to {digest!r}."
    )


def test_provider_branch_is_byte_frozen() -> None:
    # D-07 regression: provider-branch.md is byte-unchanged this phase (the
    # reference stance contract must not be applied to explanation). If this fails
    # after a deliberate edit, update PROVIDER_BRANCH_SHA256 consciously.
    digest = hashlib.sha256(_PROVIDER_BRANCH.read_bytes()).hexdigest()
    assert digest == PROVIDER_BRANCH_SHA256, (
        "skills/dogen-write/references/provider-branch.md changed — it is "
        "byte-frozen this phase (D-07 regression). If the edit is deliberate, "
        f"update PROVIDER_BRANCH_SHA256 to {digest!r}."
    )
