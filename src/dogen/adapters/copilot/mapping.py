# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

"""Anti-corruption mapping: a Copilot ``assistant.message`` event → ``DraftResult``.

This is the seam translation (ARCHITECTURE Anti-Pattern 1, RESEARCH Pitfall 4):
the SDK's ``SessionEvent`` / ``AssistantMessageData`` shapes are translated into
the pure-domain :class:`~dogen.core.models.DraftResult` here, so no vendor type
ever crosses into ``core/``. The orchestrator only ever sees ``DraftResult``.

The SDK reports ``model`` as ``str | None`` and ``output_tokens`` as ``int | None``
(an event may arrive before usage is finalised); the domain model requires
concrete values, so both are coerced to safe defaults at the boundary rather
than leaking ``None`` into the provenance record.
"""

from copilot import SessionEvent

from dogen.core.models import DraftResult

# Stand-in recorded when the runtime omits the model name on the event.
_UNKNOWN_MODEL = "unknown"
# Stand-in recorded when the runtime omits a resolved model version (WR-03):
# kept distinct from the model name so the provenance record stays honest.
_UNKNOWN_MODEL_VERSION = "unknown"


def to_draft_result(evt: SessionEvent, run_id: str) -> DraftResult:
    """Translate an ``assistant.message`` event into a domain ``DraftResult``.

    Parameters
    ----------
    evt : SessionEvent
        The final ``assistant.message`` event from ``send_and_wait``; its
        ``data`` is an ``AssistantMessageData`` carrying ``content``, ``model``,
        and ``output_tokens``.
    run_id : str
        The OTel-derived run identifier correlating this result to the trace
        (OBS-03/D-22), minted by ``core/`` and passed through unchanged.

    Returns
    -------
    DraftResult
        The drafted MyST text and its provenance inputs, in pure domain terms.
    """
    # ``evt.data`` is a union over every event payload; only an
    # ``assistant.message`` carries content/model/output_tokens. The provider
    # guarantees that event type before calling, so read the fields defensively
    # (anti-corruption: the union never reaches ``core/``).
    data = evt.data
    # Coerce ``content`` defensively (WR-05): the SDK can deliver ``content=None``
    # on a truncated/unfinalised stream. ``getattr(..., "")`` only guards a
    # *missing* attribute, not an explicit ``None``, which would flow into the
    # ``str``-typed ``DraftResult.text`` and raise a Pydantic ValidationError —
    # an uncaught crash instead of the handled degradation the seam promises.
    # Treat it like ``model``/``output_tokens``: fall back to a safe default.
    text = getattr(data, "content", None) or ""
    model = getattr(data, "model", None) or _UNKNOWN_MODEL
    model_version = getattr(data, "model_version", None) or _UNKNOWN_MODEL_VERSION
    output_tokens = getattr(data, "output_tokens", None) or 0
    return DraftResult(
        text=text,
        model=model,
        model_version=model_version,
        output_tokens=output_tokens,
        run_id=run_id,
    )
