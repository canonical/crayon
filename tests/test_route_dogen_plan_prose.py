"""Prose pins for dogen-plan's type routing (Phase 14, D-03 / D-10).

Plan 14-02 replaces dogen-plan's D-07 reference-only hard-block with real type
routing. Two invariants must hold in the skill prose, and they are pinned here
the same way ``test_id_authority_guard.py`` pins the SK-01 sentence — load-bearing
literals defined ONCE as module constants, asserted with POSITIVE presence checks:

- **The reference route is frozen (ROUTE-03, D-10).** The reference referral
  ``Next: /dogen-write — draft the unit.`` stays byte-verbatim, and
  ``reference-intake.md`` stays byte-unchanged this phase — pinned by SHA-256.
- **The routed reality is present (D-03).** The actionable referral
  ``Next: /dogen-record — walk the procedure and record the draft.`` is present,
  the two new intake references exist with their load-line, and the retired
  reference-only clamp phrase is gone.

Assertions are deliberately POSITIVE: a file-wide *absence* gate on ``/dogen-write``
would be self-invalidating — the reference route legitimately keeps ``/dogen-write``.
"""

import hashlib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOGEN_PLAN = _REPO_ROOT / "skills" / "dogen-plan" / "SKILL.md"
_REFERENCES = _REPO_ROOT / "skills" / "dogen-plan" / "references"
_REFERENCE_INTAKE = _REFERENCES / "reference-intake.md"
_ACTIONABLE_INTAKE = _REFERENCES / "actionable-intake.md"
_EXPLANATION_INTAKE = _REFERENCES / "explanation-intake.md"

# The FROZEN reference referral (ROUTE-03 / D-10) — reused byte-verbatim, never
# reworded. The reference route keeps /dogen-write; this is a POSITIVE pin.
FROZEN_REFERENCE_REFERRAL = "Next: /dogen-write — draft the unit."

# The routed actionable referral (D-03) — the verbatim grammar from README's
# frozen routing table for the `record` token.
ACTIONABLE_REFERRAL = "Next: /dogen-record — walk the procedure and record the draft."

# The retired reference-only clamp — must be gone from the routed skill.
RETIRED_CLAMP = "Accepts only the Diataxis reference direction this cycle"

# Every reference file's first body line (skills/README.md references/ convention).
INTAKE_LOAD_LINE = "Load this file at workflow step 4 (Confirm the Diataxis direction)."

# reference-intake.md is byte-frozen this phase (D-10, ROUTE-03). This is its
# current SHA-256; the test fails if a single byte changes. A legitimate future
# edit to reference-intake.md must CONSCIOUSLY update this pin.
REFERENCE_INTAKE_SHA256 = (
    "cf1ab307e8b054fcff96bd5fcada6cdd73e4ef6d24418ee038fa820ae63f1c90"
)

# --- Phase 15 (EXPL-01/EXPL-02): the intent-walk body pins -------------------
# explanation-intake.md's body is replaced this phase — the Phase-14 hard-stop
# stub becomes the real 5-whys intent walk + the four active-challenge moves.
# These are POSITIVE-presence pins on the walk body (never a file-wide absence
# gate — the reference route legitimately keeps /dogen-write elsewhere).

# The four `mp` active-challenge move names, verbatim as they appear in the walk
# body's move-set table (EXPL-02, D-05). Every name must be present.
WALK_MOVE_NAMES = (
    "glossary challenge",
    "sharpen-fuzzy-language",
    "scenario stress-testing",
    "code cross-reference",
)

# The crystallization stop rule (EXPL-01, D-02) — 5-whys is a ceiling not a
# quota; the walk ends on one reflect-back the TA confirms without new
# corrections. This short positive phrase must appear verbatim in the walk body.
CRYSTALLIZATION_STOP_MARKER = "one reflect-back, one confirmation"

# The Phase-14 hard-stop stub phrases the D-12 sweep retires. After the walk body
# lands (Task 2) none of these may appear in explanation-intake.md's body.
RETIRED_STUB_PHRASES = (
    "stops before declaring",
    "Phase 15 owns the walk body",
    "Honest hard-stop",
)


def test_frozen_reference_referral_present() -> None:
    prose = _DOGEN_PLAN.read_text(encoding="utf-8")
    assert FROZEN_REFERENCE_REFERRAL in prose, (
        "skills/dogen-plan/SKILL.md is missing the FROZEN reference referral "
        f"{FROZEN_REFERENCE_REFERRAL!r} (ROUTE-03, D-10). It is reused verbatim "
        "for the `draft` token and must never be reworded."
    )


def test_actionable_referral_present() -> None:
    prose = _DOGEN_PLAN.read_text(encoding="utf-8")
    assert ACTIONABLE_REFERRAL in prose, (
        "skills/dogen-plan/SKILL.md is missing the actionable referral "
        f"{ACTIONABLE_REFERRAL!r} (routed reality, D-03). The close block must "
        "branch on the `record` token to this verbatim line."
    )


def test_retired_clamp_phrase_is_gone() -> None:
    prose = _DOGEN_PLAN.read_text(encoding="utf-8")
    assert RETIRED_CLAMP not in prose, (
        "skills/dogen-plan/SKILL.md still carries the retired reference-only "
        f"clamp {RETIRED_CLAMP!r}. Phase 14 routes by declared direction; the "
        "clamp must be gone (D-03)."
    )


def test_reference_intake_is_byte_frozen() -> None:
    # D-10 / ROUTE-03: reference-intake.md is byte-unchanged this phase. If this
    # fails after a deliberate edit, update REFERENCE_INTAKE_SHA256 consciously.
    digest = hashlib.sha256(_REFERENCE_INTAKE.read_bytes()).hexdigest()
    assert digest == REFERENCE_INTAKE_SHA256, (
        "skills/dogen-plan/references/reference-intake.md changed — it is "
        "byte-frozen this phase (D-10, ROUTE-03). If the edit is deliberate, "
        f"update REFERENCE_INTAKE_SHA256 to {digest!r}."
    )


def test_actionable_intake_exists_with_load_line() -> None:
    assert _ACTIONABLE_INTAKE.is_file(), (
        "skills/dogen-plan/references/actionable-intake.md is missing (D-08)."
    )
    first_line = _ACTIONABLE_INTAKE.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == INTAKE_LOAD_LINE, (
        "actionable-intake.md's first body line must be exactly "
        f"{INTAKE_LOAD_LINE!r}; found {first_line!r}."
    )


def test_explanation_intake_keeps_load_line() -> None:
    # The load-line is byte-frozen (INTAKE_LOAD_LINE) even as the body is
    # replaced with the walk (D-04): the step-4 lazy-load point does not move.
    assert _EXPLANATION_INTAKE.is_file(), (
        "skills/dogen-plan/references/explanation-intake.md is missing."
    )
    first_line = _EXPLANATION_INTAKE.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == INTAKE_LOAD_LINE, (
        "explanation-intake.md's first body line must be exactly "
        f"{INTAKE_LOAD_LINE!r}; found {first_line!r}."
    )


def test_explanation_intake_names_the_four_moves() -> None:
    # EXPL-02 / D-05: the walk body carries the four active-challenge moves as a
    # named set. Every move name must be present (positive presence).
    body = _EXPLANATION_INTAKE.read_text(encoding="utf-8")
    missing = [name for name in WALK_MOVE_NAMES if name not in body]
    assert not missing, (
        "explanation-intake.md's walk body is missing move name(s) "
        f"{missing!r} (EXPL-02, D-05). All of {list(WALK_MOVE_NAMES)!r} must "
        "appear in the four-move set."
    )


def test_explanation_intake_carries_walk_body() -> None:
    # EXPL-01 / D-02: the crystallization stop rule is present — the walk ends on
    # one reflect-back the TA confirms, never a fixed-depth interrogation.
    body = _EXPLANATION_INTAKE.read_text(encoding="utf-8")
    assert CRYSTALLIZATION_STOP_MARKER in body, (
        "explanation-intake.md's walk body is missing the crystallization-stop "
        f"marker {CRYSTALLIZATION_STOP_MARKER!r} (EXPL-01, D-02). The walk must "
        "state the reflect-back-once stop rule aimed at intent."
    )


def test_explanation_intake_retires_stub_phrases() -> None:
    # D-12 sweep: the Phase-14 hard-stop language is gone from the walk body.
    body = _EXPLANATION_INTAKE.read_text(encoding="utf-8")
    still_present = [phrase for phrase in RETIRED_STUB_PHRASES if phrase in body]
    assert not still_present, (
        "explanation-intake.md still carries retired Phase-14 stub phrase(s) "
        f"{still_present!r} (D-12). The hard-stop stub language must be gone "
        "once the walk body lands."
    )
