"""RED-first: the passenger prose must mirror the canonical rubric heuristic.

The passenger authoring standard in
``skills/dogen-write/references/provider-branch.md`` is a *governed mirror* of the
domain-owned :data:`dogen.core.authoring.REFERENCE_CODE_RUBRIC`, not an independent
author. This test binds the prose to the SAME canonical :data:`RUBRIC_HEURISTIC`
symbol the driver strings use, so a one-sided edit of either locus fails loudly —
the cheap, deterministic drift guard that replaces a build-time templating system.
"""

from pathlib import Path

from dogen.core.authoring import RUBRIC_HEURISTIC, STANCE_ANCHOR

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PASSENGER_STANDARD = (
    _REPO_ROOT / "skills" / "dogen-write" / "references" / "provider-branch.md"
)


def test_passenger_prose_carries_canonical_heuristic_verbatim() -> None:
    prose = _PASSENGER_STANDARD.read_text(encoding="utf-8")
    assert RUBRIC_HEURISTIC in prose, (
        "provider-branch.md has drifted from the canonical rubric. Keep it in "
        "sync with dogen.core.authoring.REFERENCE_CODE_RUBRIC / RUBRIC_HEURISTIC."
    )


def test_passenger_prose_names_the_canonical_source() -> None:
    prose = _PASSENGER_STANDARD.read_text(encoding="utf-8")
    assert "dogen.core.authoring.REFERENCE_CODE_RUBRIC" in prose


def test_passenger_prose_carries_stance_anchor_verbatim() -> None:
    prose = _PASSENGER_STANDARD.read_text(encoding="utf-8")
    assert STANCE_ANCHOR in prose, (
        "provider-branch.md has drifted from the canonical stance contract. "
        "Keep it in sync with dogen.core.authoring.STANCE_CONTRACT / "
        "STANCE_ANCHOR."
    )


def test_passenger_prose_names_the_stance_canonical_source() -> None:
    prose = _PASSENGER_STANDARD.read_text(encoding="utf-8")
    assert "dogen.core.authoring.STANCE_CONTRACT" in prose
