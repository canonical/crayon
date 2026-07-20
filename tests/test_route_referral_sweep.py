"""Prose-pin guard for the D-03 routing-surface sweep (README + dogen-review).

Phase 14 makes every draft-stage-naming surface type-aware or provably frozen so
no hardwired ``/dogen-write`` can misroute an actionable (tutorial / how-to) unit.
This module pins the two remaining swept surfaces:

- ``skills/README.md`` — the frozen routing table now carries the ``record``-token
  referral rows (first draft, after fix, after redraft) beside the frozen
  ``draft``-token ``/dogen-write`` rows (ROUTE-01, D-03).
- ``skills/dogen-review/SKILL.md`` — the ``next_id == record`` post-verdict branch
  emits the ``/dogen-record`` fix and redraft referrals; the reference ``/dogen-write``
  arm stays intact (ROUTE-01 review side, ROUTE-03).

The literals are defined ONCE here and asserted with POSITIVE presence checks only.
A file-wide ``/dogen-write``-absence gate would be wrong and self-invalidating: the
reference route legitimately keeps ``/dogen-write`` (ROUTE-03, D-10). The record
literals are byte-identical to the strings authored in Plan 14-03 Tasks 1-2 and to
the first-draft record line emitted by dogen-plan in Plan 14-02 — one canonical
frozen grammar, quoted verbatim into every surface (D-03).
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_README = _REPO_ROOT / "skills" / "README.md"
_DOGEN_REVIEW = _REPO_ROOT / "skills" / "dogen-review" / "SKILL.md"

# --- The canonical routed record-token referral lines (frozen grammar, D-03) ---
# First-draft line — byte-identical to the string dogen-plan emits (Plan 14-02).
RECORD_FIRST_DRAFT = "Next: /dogen-record — walk the procedure and record the draft."
# After a fix verdict.
RECORD_FIX = "Next: /dogen-record — apply the recorded fix and re-record the draft."
# After a redraft verdict.
RECORD_REDRAFT = "Next: /dogen-record — re-walk the procedure and record a fresh draft."

# --- The frozen reference-token referral lines that MUST stay (ROUTE-03, D-10) ---
REFERENCE_FIRST_DRAFT = "Next: /dogen-write — draft the unit."
REFERENCE_FIX = "Next: /dogen-write — apply the recorded fix."

# --- The D-12 explanation-naming pins (Phase 15, Plan 15-03) ---
# Explanation is a first-class `/dogen-write` (`draft`-token) draft-stage direction
# alongside reference — it reuses the frozen `draft` rows verbatim, never a new token
# or referral string (D-11). These POSITIVE-presence markers pin the corrected family
# contract prose; the frozen `draft`/`record` row constants above stay untouched.
README_EXPLANATION_DRAFT_MARKER = "draft-stage skill for **reference and explanation** units"
REVIEW_EXPLANATION_DRAFT_MARKER = (
    "**reference** or **explanation** unit (token `draft`) it routes to dogen-write"
)


def test_readme_carries_the_record_first_draft_row() -> None:
    prose = _README.read_text(encoding="utf-8")
    assert RECORD_FIRST_DRAFT in prose, (
        "skills/README.md's routing table is missing the actionable first-draft "
        "record row (ROUTE-01, D-03)."
    )


def test_readme_carries_the_record_fix_row() -> None:
    prose = _README.read_text(encoding="utf-8")
    assert RECORD_FIX in prose, (
        "skills/README.md's routing table is missing the record fix row "
        "(ROUTE-01, D-03)."
    )


def test_readme_carries_the_record_redraft_row() -> None:
    prose = _README.read_text(encoding="utf-8")
    assert RECORD_REDRAFT in prose, (
        "skills/README.md's routing table is missing the record redraft row "
        "(ROUTE-01, D-03)."
    )


def test_readme_keeps_the_frozen_reference_first_draft_row() -> None:
    prose = _README.read_text(encoding="utf-8")
    assert REFERENCE_FIRST_DRAFT in prose, (
        "skills/README.md dropped the FROZEN reference first-draft referral "
        "`Next: /dogen-write — draft the unit.` — it must stay byte-identical "
        "(ROUTE-03, D-10)."
    )


def test_dogen_review_carries_the_record_fix_arm() -> None:
    prose = _DOGEN_REVIEW.read_text(encoding="utf-8")
    assert RECORD_FIX in prose, (
        "skills/dogen-review/SKILL.md is missing the `next_id == record` fix arm "
        "routing an actionable unit to /dogen-record (ROUTE-01 review side, D-02)."
    )


def test_dogen_review_carries_the_record_redraft_arm() -> None:
    prose = _DOGEN_REVIEW.read_text(encoding="utf-8")
    assert RECORD_REDRAFT in prose, (
        "skills/dogen-review/SKILL.md is missing the `next_id == record` redraft "
        "arm routing an actionable unit to /dogen-record (ROUTE-01 review side, D-02)."
    )


def test_dogen_review_keeps_the_frozen_reference_fix_arm() -> None:
    prose = _DOGEN_REVIEW.read_text(encoding="utf-8")
    assert REFERENCE_FIX in prose, (
        "skills/dogen-review/SKILL.md dropped the frozen reference fix arm "
        "`Next: /dogen-write — apply the recorded fix.` — the `draft`-token "
        "/dogen-write route must stay intact (ROUTE-03)."
    )


def test_readme_names_explanation_on_the_draft_route() -> None:
    prose = _README.read_text(encoding="utf-8")
    assert README_EXPLANATION_DRAFT_MARKER in prose, (
        "skills/README.md's dogen-write family-contract bullet must name "
        "explanation alongside reference as a `/dogen-write` (`draft`-token) "
        "draft-stage direction — the family contract no longer implies reference "
        "is the only `/dogen-write` direction (D-12)."
    )


def test_dogen_review_draft_arm_covers_explanation() -> None:
    prose = _DOGEN_REVIEW.read_text(encoding="utf-8")
    assert REVIEW_EXPLANATION_DRAFT_MARKER in prose, (
        "skills/dogen-review/SKILL.md's fix/redraft routing prose must name "
        "explanation on the `draft`→/dogen-write arm (an explanation unit rides "
        "`draft`, never `record`, exactly like reference) (D-12)."
    )
