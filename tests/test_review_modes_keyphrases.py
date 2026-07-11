"""RED-first: pin the dogen-review two-mode + findings-framework design intent.

This deterministic prose guard fixes the design of the reworked ``dogen-review``
skill into a test so the rewrite cannot silently regress. It asserts, over the
``dogen-review`` ``SKILL.md`` and its ``references/review-rubric.md``:
the two selectable modes (record vs review) are present; the three finding
priorities appear as bracketed tags; the four review dimensions are named; the
CLI run-status vocabulary is never repurposed as a bracketed finding tag (the
D-03 collision guard, the crux); the removed raw-MyST-dump phrasing is gone; and
the code-dump rubric copy is bound verbatim to the single source of truth in
:mod:`dogen.core.authoring`. It is RED against the current tree (review-rubric.md
does not exist yet and SKILL.md still carries the dump wording).
"""

from pathlib import Path

from dogen.core.authoring import RUBRIC_HEURISTIC

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = _REPO_ROOT / "skills" / "dogen-review" / "SKILL.md"
_RUBRIC = _REPO_ROOT / "skills" / "dogen-review" / "references" / "review-rubric.md"
_PROVENANCE = (
    _REPO_ROOT / "skills" / "dogen-review" / "references" / "provenance-summary.md"
)

# The model-provenance surface (MODEL-04): dogen-review must surface model_origin
# in its provenance summary, and the field map must explain the D-03 vouch vocab.
_ORIGIN_KEY = "model_origin"
_ORIGIN_VOCAB = ("`ta`", "`self`", "`config`", "`flag`")

# The review-findings priority axis — the ONLY finding-tag vocabulary.
_PRIORITIES = ("must-fix", "should-fix", "nit")

# The four generalized review dimensions for a Diataxis reference unit.
_DIMENSIONS = ("source-fidelity", "completeness", "structure-fit", "clarity")

# The two selectable entry modes.
_MODES = ("record", "review")

# SK-02: dimension 0 "objective check" is the new FIRST rubric dimension. Its
# failure is must-fix by definition (the severity floor), pinned to the EXISTING
# [must-fix] tag — never a fourth priority. A multi-file unit's cross-page
# consistency check must quote the diverging lines (D-02).
_OBJECTIVE_CHECK = "objective check"
_SEVERITY_FLOOR = "must-fix by definition"
_CROSS_PAGE_HEADING = "Cross-page consistency"
_CROSS_PAGE_QUOTE_PHRASE = "quote the diverging lines"

# The CLI machine surface: failure reason codes + progress states. None of these
# may ever be repurposed as a bracketed finding tag (D-03 collision guard).
_RUN_STATUS_TOKENS = (
    "signoff_required",
    "backend_unavailable",
    "model_rejected",
    "unit_exists",
    "not_drafted",
    "already_accepted",
    "target_exists",
    "bad_report",
    "pending",
    "sourced",
    "drafted",
    "reviewed",
)

# The exact removed step-2 dump phrasings that must be absent from the rewrite.
_REMOVED_DUMP_LITERALS = (
    "Present the draft inline",
    "drafted MyST source inline",
)


def _read(path: Path) -> str:
    """Return the UTF-8 text of ``path``.

    Parameters
    ----------
    path : Path
        The file to read.

    Returns
    -------
    str
        The file's decoded contents.
    """
    return path.read_text(encoding="utf-8")


def test_both_modes_present_as_selectable_modes() -> None:
    """Both mode names appear across the combined SKILL.md + rubric text."""
    combined = _read(_SKILL) + _read(_RUBRIC)
    for mode in _MODES:
        assert mode in combined, f"mode {mode!r} missing from the review skill text"


def test_each_priority_appears_bracketed_in_rubric() -> None:
    """Each finding priority appears in bracketed tag form in review-rubric.md."""
    rubric = _read(_RUBRIC)
    for priority in _PRIORITIES:
        assert f"[{priority}]" in rubric, (
            f"priority tag [{priority}] missing from review-rubric.md"
        )


def test_all_four_dimensions_present() -> None:
    """All four review dimensions are named across the combined text."""
    combined = _read(_SKILL) + _read(_RUBRIC)
    for dimension in _DIMENSIONS:
        assert dimension in combined, (
            f"dimension {dimension!r} missing from the review skill text"
        )


def test_dimension_zero_objective_check_named() -> None:
    """review-rubric.md names the dimension 0 'objective check' (SK-02).

    Dimension 0 is a fifth named concept layered ahead of the four generalized
    dimensions; it must NOT reduce or rename them (``_DIMENSIONS`` stays intact).
    """
    rubric = _read(_RUBRIC)
    assert _OBJECTIVE_CHECK in rubric, (
        "review-rubric.md must name the dimension 0 'objective check' (SK-02)"
    )


def test_dimension_zero_states_must_fix_severity_floor() -> None:
    """An objective-check failure is must-fix by definition, reusing [must-fix] (SK-02).

    The severity floor pins objective-check failures to the EXISTING ``[must-fix]``
    tag — it must never invent a fourth priority (collision guard, D-03).
    """
    rubric = _read(_RUBRIC)
    assert _SEVERITY_FLOOR in rubric, (
        "review-rubric.md must state the objective-check severity floor "
        f"({_SEVERITY_FLOOR!r})"
    )
    assert "[must-fix]" in rubric, (
        "the severity floor must reuse the existing [must-fix] tag, not a new one"
    )


def test_cross_page_check_requires_quoting_diverging_lines() -> None:
    """The multi-file cross-page consistency check quotes the diverging lines (D-02).

    SK-02 strengthens the EXISTING structure-fit cross-page check from "label each
    finding with its page path" to also quote the diverging lines.
    """
    rubric = _read(_RUBRIC)
    assert _CROSS_PAGE_HEADING in rubric, (
        "the structure-fit cross-page consistency check must remain present"
    )
    assert "quote" in rubric, "the cross-page check must require quoting"
    assert _CROSS_PAGE_QUOTE_PHRASE in rubric, (
        f"the cross-page check must {_CROSS_PAGE_QUOTE_PHRASE!r} (SK-02 line-quoting)"
    )


def test_run_status_tokens_never_bracketed_as_finding_tags() -> None:
    """No CLI run-status token is repurposed as a bracketed finding tag (D-03).

    The check is scoped to the bracketed tag shape (``[token]``) so legitimate
    prose mentions of reason codes and the ``- [ ]`` success-criteria checkboxes
    do not false-positive.
    """
    skill = _read(_SKILL)
    rubric = _read(_RUBRIC)
    for token in _RUN_STATUS_TOKENS:
        bracketed = f"[{token}]"
        assert bracketed not in skill, (
            f"run-status token {bracketed} used as a finding tag in SKILL.md "
            "(D-03 collision)"
        )
        assert bracketed not in rubric, (
            f"run-status token {bracketed} used as a finding tag in review-rubric.md "
            "(D-03 collision)"
        )


def test_removed_raw_dump_phrasing_absent() -> None:
    """The old step-2 raw-MyST-dump phrasings are gone from the rewritten SKILL.md."""
    skill = _read(_SKILL)
    for literal in _REMOVED_DUMP_LITERALS:
        assert literal not in skill, (
            f"removed dump phrasing {literal!r} still present in SKILL.md"
        )


def test_rubric_carries_canonical_heuristic_verbatim() -> None:
    """review-rubric.md carries the canonical RUBRIC_HEURISTIC string verbatim.

    Binds the reviewer's code-dump copy to the writer's single source of truth in
    :data:`dogen.core.authoring.RUBRIC_HEURISTIC` so the third mirror cannot drift.
    """
    rubric = _read(_RUBRIC)
    assert RUBRIC_HEURISTIC in rubric, (
        "review-rubric.md has drifted from the canonical rubric. Keep it in sync "
        "with dogen.core.authoring.REFERENCE_CODE_RUBRIC / RUBRIC_HEURISTIC."
    )


def test_rubric_names_the_canonical_code_rubric_source() -> None:
    """review-rubric.md names the canonical dogen.core.authoring source symbol."""
    rubric = _read(_RUBRIC)
    assert "dogen.core.authoring.REFERENCE_CODE_RUBRIC" in rubric


def test_provenance_summary_surfaces_model_origin() -> None:
    """dogen-review surfaces model_origin + the D-03 vouch vocab (MODEL-04).

    Pins the model-provenance surface so the rewrite cannot silently drop it:
    ``model_origin`` must appear both in the SKILL.md ``### Provenance`` output
    block and in the ``provenance-summary.md`` field map, and the field map must
    explain the D-03 origin vocabulary (``ta``/``self``/``config``/``flag``) so
    the reviewer reads on whose authority the model was recorded.
    """
    skill = _read(_SKILL)
    provenance = _read(_PROVENANCE)
    assert _ORIGIN_KEY in skill, (
        f"{_ORIGIN_KEY} missing from the dogen-review SKILL.md provenance block"
    )
    assert _ORIGIN_KEY in provenance, (
        f"{_ORIGIN_KEY} missing from the provenance-summary.md field map"
    )
    for value in _ORIGIN_VOCAB:
        assert value in provenance, (
            f"D-03 origin vocab {value} missing from provenance-summary.md"
        )
