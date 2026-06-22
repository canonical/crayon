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

from copilot import SessionEvent, SessionEventType

from dogen.core.models import DraftResult

# Stand-in recorded when the runtime omits the model name on the event.
_UNKNOWN_MODEL = "unknown"
# Stand-in recorded when the runtime omits a resolved model version (WR-03):
# kept distinct from the model name so the provenance record stays honest.
_UNKNOWN_MODEL_VERSION = "unknown"

# Built-in tools whose argument carries a guaranteed content read (D-02): only
# ``view`` opens a concrete file. ``grep``/``glob`` are discovery tools whose
# path is a search scope, not a read — they record the tool, never an origin.
_CONTENT_READ_TOOLS = frozenset({"view"})
# The CLI-owned argument key under which ``view`` reports the read file path.
# Centralised so a CLI rename localises to this one constant (RESEARCH Pitfall 4):
# a drift degrades to honest-empty (never a crash), confirmed by one manual run.
_VIEW_PATH_KEY = "path"
# Source qualifier for the closed READONLY set — all built-ins, so a fixed
# ``builtin:`` prefix is correct (D-03; built-ins report ``mcp_server_name=None``).
_BUILTIN_PREFIX = "builtin:"


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


def tool_events_to_provenance(
    events: list[SessionEvent],
) -> tuple[list[str], list[str]]:
    """Derive observed ``(context_origins, tools_used)`` from session events.

    The seam translation for what the agent actually read/ran (PROV-01/02,
    BL-01): the SDK's ``SessionEvent`` history is reduced to two pure-domain
    ``list[str]`` here, so no vendor shape crosses into ``core/`` (D-04/SEAM-01).
    Only ``TOOL_EXECUTION_START`` events carry ``tool_name``/``arguments`` — the
    matching ``TOOL_EXECUTION_COMPLETE`` has neither — so START events are
    counted exclusively (no double count; RESEARCH Pitfall 1). Both lists are
    first-seen de-duped (D-03), and every field is read defensively so a
    malformed event degrades to honest-empty rather than crashing the draft
    (omit-on-doubt, D-02/D-05/V5; threat T-04-01).

    Parameters
    ----------
    events : list of SessionEvent
        The complete chronological session history from ``session.get_events()``.

    Returns
    -------
    tuple of (list of str, list of str)
        ``context_origins`` — the concrete file paths content-read tools opened
        (only ``view``'s ``path``), first-seen de-duped; and ``tools_used`` —
        the ``builtin:<name>`` identifiers the agent invoked, first-seen
        de-duped. Both empty when no tool events were observed (honest-empty).
    """
    context_origins: list[str] = []
    tools_used: list[str] = []
    for evt in events:
        # name + arguments ride only on START; COMPLETE carries neither, so
        # filtering START exclusively avoids a double count (Pitfall 1).
        if evt.type is not SessionEventType.TOOL_EXECUTION_START:
            continue
        data = evt.data
        name = getattr(data, "tool_name", "") or ""
        if not name:
            continue
        qualified = f"{_BUILTIN_PREFIX}{name}"
        if qualified not in tools_used:
            tools_used.append(qualified)
        if name in _CONTENT_READ_TOOLS:
            # ``arguments`` is typed ``Any`` (the raw CLI dict) — guard it:
            # a None / non-dict / non-str path records no origin (Pitfall 2).
            args = getattr(data, "arguments", None)
            path = args.get(_VIEW_PATH_KEY) if isinstance(args, dict) else None
            if isinstance(path, str) and path and path not in context_origins:
                context_origins.append(path)
    return context_origins, tools_used
