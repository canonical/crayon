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

"""The real Copilot drafting provider — the sole ``github-copilot-sdk`` importer.

:class:`CopilotDraftingProvider` implements the same ``core.ports.DraftingProvider``
port the deterministic mock proved (SEAM-03 swappability from both sides), so the
orchestrator drives it unchanged. It opens a bounded read-only Copilot session
(allowlist ``grep``/``glob``/``view`` from :mod:`.tools`), sends the composed
drafting prompt, and translates the result through :func:`.mapping.to_draft_result`
so no SDK shape reaches ``core/``.

A down, unauthenticated, or transport-broken backend (Copilot CLI auto-update
breaking JSON-RPC, issue #1606) is converted into a handled
:class:`BackendUnavailableError` — a clear message and a nonzero CLI exit, never
a crash (SKEL-05/D-27, threat T-02.3-03).

Runtime facts honoured here (confirmed against the authenticated CLI ``1.0.64-0``):

* ``create_session`` is a **coroutine** — it must be ``await``ed, and its result
  is itself an async context manager (RESEARCH Pitfall 2).
* ``working_directory`` **must be an absolute path** — a relative value such as
  ``"."`` is rejected with JSON-RPC ``-32603`` ("Directory path must be absolute").
"""

import os
from collections.abc import Iterable

from copilot import (
    CopilotClient,
    SessionEvent,
    SessionEventType,
    StopError,
)
from copilot.session import SystemMessageAppendConfig

from dogen.adapters.copilot.mapping import to_draft_result
from dogen.adapters.copilot.tools import DENY, READONLY
from dogen.core.models import (
    DraftResult,
    Effort,
    Intent,
    SourceRef,
    Steering,
)

# Default drafting model and per-pass effort for the skeleton.
_DEFAULT_MODEL = "gpt-5"
_DEFAULT_EFFORT: Effort = Effort.medium
# send_and_wait timeout (seconds) — the SDK default, made explicit here.
_DRAFT_TIMEOUT = 120.0


class BackendUnavailableError(RuntimeError):
    """The Copilot backend is down, unauthenticated, or its transport broke.

    Raised instead of letting a raw SDK/connection failure crash the loop, so
    the CLI can surface a clear message and a nonzero exit (SKEL-05/D-27).
    """


class CopilotDraftingProvider:
    """A real :class:`~dogen.core.ports.DraftingProvider` on the Copilot SDK.

    Parameters
    ----------
    model : str
        The drafting model to request; defaults to the skeleton's ``gpt-5``.
    effort : Effort
        The reasoning effort for the pass; defaults to ``medium``.
    working_directory : str or None
        Absolute repo-root path the session looks up sources in. ``None``
        resolves to the current working directory (always made absolute).
    """

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        effort: Effort = _DEFAULT_EFFORT,
        working_directory: str | None = None,
    ) -> None:
        self._model = model
        self._effort = effort
        # The SDK rejects a relative working_directory; resolve to absolute.
        self._working_directory = os.path.abspath(working_directory or os.getcwd())

    async def draft_unit(
        self,
        *,
        intent: Intent,
        audience: str,
        steering: Steering,
        sources: list[SourceRef],
    ) -> DraftResult:
        """Draft one unit on the real Copilot SDK behind the shared port.

        Parameters
        ----------
        intent : Intent
            The Diátaxis direction to draft toward.
        audience : str
            Who the page is written for.
        steering : Steering
            The recorded HITL steering event that precedes this draft.
        sources : list of SourceRef
            The human-pointed sources to ground the draft in.

        Returns
        -------
        DraftResult
            The drafted MyST content plus provenance inputs, in domain terms.

        Raises
        ------
        BackendUnavailableError
            If the backend is unavailable, unauthenticated, or its transport
            broke (a handled state, never a crash — SKEL-05/D-27).
        """
        prompt = _compose_prompt(intent, audience, sources)
        steer = _compose_steering(intent, audience, steering)
        try:
            return await self._run_draft(prompt, steer)
        except StopError as exc:
            raise BackendUnavailableError(
                f"Copilot backend stopped unexpectedly: {exc}"
            ) from exc
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise BackendUnavailableError(
                f"Copilot backend is unavailable: {exc}"
            ) from exc

    async def _run_draft(self, prompt: str, steer: str) -> DraftResult:
        """Open a bounded session, send the prompt, and map the result.

        Parameters
        ----------
        prompt : str
            The composed drafting instruction.
        steer : str
            The system-message steering text (intent + audience).

        Returns
        -------
        DraftResult
            The mapped domain result.

        Raises
        ------
        BackendUnavailableError
            If the pre-flight status check reports an unhealthy backend.
        """
        async with CopilotClient() as client:
            await _require_available_backend(client)
            session_cm = await client.create_session(
                model=self._model,
                reasoning_effort=self._effort.value,
                available_tools=READONLY,
                excluded_tools=DENY,
                working_directory=self._working_directory,
                system_message=SystemMessageAppendConfig(mode="append", content=steer),
            )
            async with session_cm as session:
                event = await session.send_and_wait(prompt, timeout=_DRAFT_TIMEOUT)
        return _require_assistant_message(event)


async def _require_available_backend(client: CopilotClient) -> None:
    """Fail fast with a handled error if the backend is not ready.

    Parameters
    ----------
    client : CopilotClient
        The connected SDK client to probe.

    Raises
    ------
    BackendUnavailableError
        If status or auth-status reports the backend cannot serve a draft.
    """
    try:
        await client.get_status()
        await client.get_auth_status()
    except StopError as exc:
        raise BackendUnavailableError(
            f"Copilot backend status check failed: {exc}"
        ) from exc
    except (ConnectionError, OSError, TimeoutError) as exc:
        raise BackendUnavailableError(f"Copilot backend is unreachable: {exc}") from exc


def _require_assistant_message(event: SessionEvent | None) -> DraftResult:
    """Translate the final event into a ``DraftResult`` or fail clearly.

    Parameters
    ----------
    event : SessionEvent or None
        The final event returned by ``send_and_wait``.

    Returns
    -------
    DraftResult
        The mapped domain result.

    Raises
    ------
    BackendUnavailableError
        If no ``assistant.message`` event was produced (no draft to map).
    """
    if event is None or event.type is not SessionEventType.ASSISTANT_MESSAGE:
        raise BackendUnavailableError(
            "Copilot returned no assistant message to draft from"
        )
    # run_id is stamped by core/ from the active OTel trace; the adapter is not
    # the owner of correlation, so it passes through an empty placeholder that
    # the orchestrator overwrites when recording the generation.
    return to_draft_result(event, run_id="")


def _compose_prompt(intent: Intent, audience: str, sources: Iterable[SourceRef]) -> str:
    """Compose the drafting instruction from domain inputs only.

    Parameters
    ----------
    intent : Intent
        The Diátaxis direction.
    audience : str
        The target audience.
    sources : iterable of SourceRef
        The human-pointed sources to ground the draft in.

    Returns
    -------
    str
        A plain-text drafting prompt carrying no SDK shapes.
    """
    listed = ", ".join(s.path or s.ref or "" for s in sources) or "no sources"
    return (
        f"Draft a {intent.value} documentation page for {audience}, in MyST "
        f"Markdown suitable for Sphinx. Ground it strictly in these sources: "
        f"{listed}. Use only the read-only tools available to inspect them."
    )


def _compose_steering(intent: Intent, audience: str, steering: Steering) -> str:
    """Compose the system-message steering text from the recorded HITL event.

    Parameters
    ----------
    intent : Intent
        The steered Diátaxis direction.
    audience : str
        The steered audience.
    steering : Steering
        The recorded steering event (its author anchors accountability).

    Returns
    -------
    str
        The steering text appended to the session's system message.
    """
    return (
        f"You are drafting documentation under human steering recorded by "
        f"{steering.author}. Direction: {intent.value}. Audience: {audience}. "
        "Draft only; never commit, push, or modify files."
    )
