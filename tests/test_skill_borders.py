"""RED-first: SK-05 border normalization across the three dogen skills.

Round-3 finding H was border drift: dogen-plan carried no ``<output_specification>``
at all, and the open/close shapes each leg improvised diverged (bare vs backticked
referrals, no state check, inconsistent close blocks). SK-05 normalizes the family
to ONE shared border shape:

- **OPEN** — every skill confirms the target unit and performs a state check (the
  unit's current lifecycle state) before the main workflow.
- **CLOSE** — every skill ends with an output block carrying the ``git: committed``
  relay line(s) and the frozen ``Next: /dogen-<skill> — <imperative>.`` referral.

dogen-write's ``<objective>`` open and ``<output_specification>`` close are the
canonical shape the other two are normalized TO. This guard pins the shared shape
so it cannot silently re-drift (round 3 proved re-wording drifts).
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS = _REPO_ROOT / "skills"
_PLAN = _SKILLS / "dogen-plan" / "SKILL.md"
_WRITE = _SKILLS / "dogen-write" / "SKILL.md"
_REVIEW = _SKILLS / "dogen-review" / "SKILL.md"
_ALL_THREE = (_PLAN, _WRITE, _REVIEW)


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
