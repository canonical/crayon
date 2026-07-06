"""RED-first: the driver strings must carry the code-in-narrative rubric.

Both authoring strings the Copilot driver composes — the per-turn drafting
prompt (:func:`~dogen.adapters.copilot.provider._compose_prompt`) and the durable
system-message steering (:func:`_compose_steering`) — must interpolate the
canonical ``dogen.core.authoring`` rubric so the model is told what may *surface*
in the output, not only what it may *read*. Reading the sources stays mandatory;
reproducing their source is newly forbidden by default. The rubric lives in the
domain layer (seam-legal for the adapter to import); ``RUBRIC_HEURISTIC`` is the
single canonical anchor the drift-guard test (``test_rubric_drift_guard.py``)
also binds the passenger prose to.
"""

from dogen.adapters.copilot.provider import _compose_prompt, _compose_steering
from dogen.core.authoring import REFERENCE_CODE_RUBRIC, RUBRIC_HEURISTIC
from dogen.core.models import Intent, Signoff


def _steering() -> Signoff:
    return Signoff(
        author="a@example.com",
        at="2026-07-03T00:00:00Z",
        intent=Intent.reference,
        audience="operators",
    )


def test_compose_prompt_carries_rubric_heuristic() -> None:
    prompt = _compose_prompt(Intent.reference, "operators", [], [])
    assert RUBRIC_HEURISTIC in prompt


def test_compose_prompt_keeps_read_scope_and_adds_output_scope() -> None:
    prompt = _compose_prompt(Intent.reference, "operators", [], [])
    # Reading the sources stays mandatory (v1: starting points, not a boundary),
    # and every claim must still trace to something actually read ...
    assert "Start from these declared sources" in prompt
    assert "ground every claim in what you actually read" in prompt
    assert "never assert what you have not read" in prompt
    # ... and reproducing them is now forbidden by default (output-scope rule).
    assert "qualified name" in prompt
    assert REFERENCE_CODE_RUBRIC in prompt


def test_compose_steering_carries_rubric() -> None:
    steer = _compose_steering(Intent.reference, "operators", _steering())
    assert RUBRIC_HEURISTIC in steer
    assert REFERENCE_CODE_RUBRIC in steer


def test_heuristic_is_verbatim_substring_of_rubric() -> None:
    # The anchor is genuinely part of the canonical text, not a hand-copied twin.
    assert RUBRIC_HEURISTIC in REFERENCE_CODE_RUBRIC
