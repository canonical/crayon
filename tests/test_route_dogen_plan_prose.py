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


def test_explanation_intake_exists_with_load_line() -> None:
    assert _EXPLANATION_INTAKE.is_file(), (
        "skills/dogen-plan/references/explanation-intake.md is missing (D-05)."
    )
    first_line = _EXPLANATION_INTAKE.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == INTAKE_LOAD_LINE, (
        "explanation-intake.md's first body line must be exactly "
        f"{INTAKE_LOAD_LINE!r}; found {first_line!r}."
    )
