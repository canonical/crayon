"""RED-first: the id-authority precedence rule must be byte-identical in both loci.

Round-3 finding F was unit-id drift: three legs coined three different ids while
the prescribed id was on screen, because ``skills/README.md`` said *propose* the
id and ``skills/dogen-plan/SKILL.md`` said *collect* it — contradictory guidance.
SK-01 fixes this with ONE precedence sentence, verbatim-identical in both files:
a TA-/brief-supplied id is used as given; the skill proposes one only when none
was supplied.

This test binds that canonical sentence into BOTH skill files, so a one-sided
edit of either locus (or any byte-level drift between them) fails loudly — the
cheap, deterministic drift guard that makes the id-drift class impossible.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_README = _REPO_ROOT / "skills" / "README.md"
_DOGEN_PLAN = _REPO_ROOT / "skills" / "dogen-plan" / "SKILL.md"

# The canonical id-authority sentence. Defined ONCE here and asserted present in
# BOTH skill files — the byte-identity is enforced in code, not by convention.
ID_AUTHORITY_SENTENCE = (
    "A TA- or brief-supplied unit id is used verbatim; "
    "propose an id only when none is supplied."
)


def test_id_authority_sentence_in_readme() -> None:
    prose = _README.read_text(encoding="utf-8")
    assert ID_AUTHORITY_SENTENCE in prose, (
        "skills/README.md is missing the canonical id-authority sentence (SK-01). "
        "It must carry the sentence verbatim in the Smart-defaults block."
    )


def test_id_authority_sentence_in_dogen_plan() -> None:
    prose = _DOGEN_PLAN.read_text(encoding="utf-8")
    assert ID_AUTHORITY_SENTENCE in prose, (
        "skills/dogen-plan/SKILL.md is missing the canonical id-authority "
        "sentence (SK-01). It must carry the sentence verbatim in step 3."
    )


def test_id_authority_sentence_byte_identical_across_files() -> None:
    readme = _README.read_text(encoding="utf-8")
    plan = _DOGEN_PLAN.read_text(encoding="utf-8")
    # The exact same string is `in` both texts — byte-for-byte, no drift.
    assert ID_AUTHORITY_SENTENCE in readme and ID_AUTHORITY_SENTENCE in plan, (
        "The id-authority sentence has drifted between skills/README.md and "
        "skills/dogen-plan/SKILL.md. Keep the precedence rule byte-identical "
        "in both loci (SK-01)."
    )
