"""ROUTE-03 regression guard: the reference (and explanation) routing is untouched.

The phase safety net for the type-aware ``_suggest_next`` (Plan 14-01). The core
routing decision gains a keyword-only ``intent`` and a new ``record`` token for
tutorial/how-to units at the draft-stage fork; this file proves the *other* two
directions are provably **byte-identical** to the pre-phase output.

Mirrors the EVID-06 byte-identity pattern in ``tests/test_step_free_regression.py``:
enumerate every reachable lifecycle combination and assert
``_suggest_next(..., intent=Intent.reference)`` returns a hard-coded expected
``(token, next)`` table identical to today, and that ``intent=Intent.explanation``
returns the SAME table (explanation rides the existing tokens — it NEVER emits
``record``; D-06). ``fix``/``redraft`` still collapse to the ``draft`` token;
``sign_off``/``re_sign``/``review``/``publish`` are unchanged.

Fully offline: pure calls into the routing function, no store, no git (D-17).
"""

from dogen.core.models import Intent, ProgressState, ReviewVerdict
from dogen.core.orchestrator import _suggest_next

_UNIT = "u"

#: Every reachable ``(state, signed_off, stale_plan, last_verdict)`` combination
#: mapped to the exact ``(token, next)`` the pre-phase ``_suggest_next`` produced.
#: The ``done`` key is unreachable (``ProgressState`` has exactly three members),
#: so it is intentionally absent. This table IS the ROUTE-03 acceptance surface.
_EXPECTED: list[tuple[ProgressState, bool, bool, ReviewVerdict | None, str, str]] = [
    # unsigned → sign_off (stale is ignored until a signoff exists)
    (ProgressState.pending, False, False, None, "sign_off", "dogen signoff u"),
    (ProgressState.pending, False, True, None, "sign_off", "dogen signoff u"),
    (ProgressState.drafted, False, False, None, "sign_off", "dogen signoff u"),
    # signed but the plan changed after signoff → re_sign
    (
        ProgressState.pending,
        True,
        True,
        None,
        "re_sign",
        "dogen signoff u --re-sign  # plan changed since signoff",
    ),
    (
        ProgressState.reviewed,
        True,
        True,
        ReviewVerdict.fix,
        "re_sign",
        "dogen signoff u --re-sign  # plan changed since signoff",
    ),
    # signed, fresh plan → the lifecycle ladder
    (ProgressState.pending, True, False, None, "draft", "dogen draft u"),
    (ProgressState.drafted, True, False, None, "review", "dogen review u"),
    (
        ProgressState.reviewed,
        True,
        False,
        ReviewVerdict.accept,
        "publish",
        "accepted — the publishing commit/PR is yours",
    ),
    # fix / redraft both collapse to the `draft` token (append-only vocabulary)
    (
        ProgressState.reviewed,
        True,
        False,
        ReviewVerdict.fix,
        "draft",
        "dogen draft u  # apply the recorded fix",
    ),
    (
        ProgressState.reviewed,
        True,
        False,
        ReviewVerdict.redraft,
        "draft",
        "dogen draft u  # re-draft per the recorded steering",
    ),
    # a reviewed unit with no recorded verdict rides the redraft branch (unchanged)
    (
        ProgressState.reviewed,
        True,
        False,
        None,
        "draft",
        "dogen draft u  # re-draft per the recorded steering",
    ),
]


def test_reference_routing_is_byte_identical() -> None:
    # ROUTE-03: a reference unit's (token, next) tuple is byte-identical to the
    # pre-phase output at every reachable lifecycle combination.
    for state, signed, stale, verdict, token, nxt in _EXPECTED:
        assert _suggest_next(
            state,
            signed_off=signed,
            stale_plan=stale,
            last_verdict=verdict,
            unit_id=_UNIT,
            intent=Intent.reference,
        ) == (token, nxt), (state, signed, stale, verdict)


def test_explanation_rides_the_same_tokens_as_reference() -> None:
    # ROUTE-02 core / D-06: an explanation unit rides the existing tokens exactly
    # — it NEVER emits `record`; its table is identical to the reference table.
    for state, signed, stale, verdict, token, nxt in _EXPECTED:
        assert _suggest_next(
            state,
            signed_off=signed,
            stale_plan=stale,
            last_verdict=verdict,
            unit_id=_UNIT,
            intent=Intent.explanation,
        ) == (token, nxt), (state, signed, stale, verdict)


def test_explanation_never_emits_record_token() -> None:
    # Defensive: no reachable combination routes an explanation unit to `record`.
    for state, signed, stale, verdict, _token, _nxt in _EXPECTED:
        got, _ = _suggest_next(
            state,
            signed_off=signed,
            stale_plan=stale,
            last_verdict=verdict,
            unit_id=_UNIT,
            intent=Intent.explanation,
        )
        assert got != "record", (state, signed, stale, verdict)
