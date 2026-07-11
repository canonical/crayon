"""RED-first: the plan declaration ceremony must be batched (SK-03 / D-04).

Round-3 finding H was ceremony friction: dogen-plan step 6 narrated
``dogen unit new``, ``dogen unit edit --body-file -``, and ``dogen signoff`` as
three separate per-verb blocks, each quoting its own ``git: committed <sha7>``
line. SK-03 collapses them: after ONE reflect-back confirmation the three verbs
run back-to-back and the skill presents ONE summary block carrying all three
``git: committed`` lines. Per D-04 a mid-batch failure STOPS, prints exactly what
landed, and prints the single resume command ``dogen signoff <id>`` — no rollback.

This test pins those keyphrases into dogen-plan step 6 so the batched shape
cannot silently regress to the per-verb narration.
"""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOGEN_PLAN = _REPO_ROOT / "skills" / "dogen-plan" / "SKILL.md"


def _step_6() -> str:
    text = _DOGEN_PLAN.read_text(encoding="utf-8")
    start = text.index("<step_6")
    end = text.index("</step_6>", start)
    return text[start:end]


def test_ceremony_runs_three_verbs_after_one_confirmation() -> None:
    step6 = _step_6().lower()
    assert "after one confirmation" in step6, (
        "step 6 no longer states the three verbs run after ONE confirmation (SK-03)."
    )
    for verb in ("dogen unit new", "dogen unit edit", "dogen signoff"):
        assert verb in step6, f"step 6 no longer names {verb!r} (SK-03)."


def test_ceremony_presents_one_batched_summary_block() -> None:
    step6 = _step_6().lower()
    assert "one summary block" in step6, (
        "step 6 no longer describes ONE batched summary block (SK-03)."
    )
    assert "git: committed" in step6, (
        "step 6 no longer quotes the git: committed relay (SK-03)."
    )


def test_ceremony_midbatch_failure_prints_single_resume_hint() -> None:
    step6 = _step_6().lower()
    # D-04: a mid-batch failure stops, prints what landed, and prints the single
    # resume command `dogen signoff <id>` — it does NOT roll back.
    assert "dogen signoff <id>" in step6, (
        "step 6's mid-batch failure branch must print the single resume "
        "command `dogen signoff <id>` (D-04)."
    )
    assert "roll back" in step6 or "rollback" in step6, (
        "step 6's mid-batch failure branch must state the no-rollback rule (D-04)."
    )
