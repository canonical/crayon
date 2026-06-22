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

"""Shared fake-SDK harness for the Copilot adapter tests (no network, D-24).

The Wave-1 implementation tests (``test_copilot_session_kwargs.py``,
``test_copilot_model_selection.py``, ``test_copilot_error_mapping.py`` in plan
03-02) all drive the real
:class:`~dogen.adapters.copilot.provider.CopilotDraftingProvider`
against a stubbed ``CopilotClient`` injected at the true SDK boundary
(``dogen.adapters.copilot.provider.CopilotClient``). No live SDK call or network
access occurs — pytest only ever touches these stubs.

The harness gives those tests three things:

* :class:`_StubClient` — records the ``create_session(**kwargs)`` it received in
  ``session_kwargs`` (so a test can assert the model / effort / permission handler
  the provider asked for) and, on the happy path, returns a scripted
  :class:`_StubSession`.
* :class:`_StubSession` — an async context manager whose ``send_and_wait``
  yields a scripted ``assistant.message`` event so ``_require_assistant_message``
  passes, or raises a scripted exception (how the 03-02 error-mapping tests
  inject a fake ``JsonRpcError``).
* :func:`install_stub_client` — a fixture returning a callable that builds a
  stub from a keyword recipe, monkeypatches the SDK boundary, and returns the
  stub instance so the test can read ``session_kwargs``.

The ``_steering`` / ``_draft`` helpers drive a single draft through the provider,
hoisted here so the 03-02 tests do not redefine them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from dogen.adapters.copilot.provider import CopilotDraftingProvider
from dogen.core.models import DraftResult, Intent, SourceRef, Steering

if TYPE_CHECKING:
    # SDK types are referenced only in type annotations here (deferred by
    # ``from __future__ import annotations``). Keeping the import behind
    # ``TYPE_CHECKING`` means importing this shared ``conftest`` puts no
    # ``copilot`` entry in ``sys.modules`` — so a mock-path runtime isolation
    # check stays meaningful (WR-02). The single runtime use of the SDK types
    # lives in a function-local import inside ``_assistant_event``.
    from copilot import SessionEvent, SessionEventType


@dataclass
class _StubAssistantData:
    """A minimal stand-in for the SDK ``AssistantMessageData`` payload.

    The mapping layer (:func:`dogen.adapters.copilot.mapping.to_draft_result`)
    reads only ``content`` / ``model`` / ``output_tokens`` / ``model_version`` by
    attribute, so a structural fake is sufficient — no SDK payload is constructed.

    Attributes
    ----------
    content : str
        The drafted MyST text the assistant returned.
    model : str
        The model name the runtime reported on the event.
    output_tokens : int
        The output-token count the runtime reported.
    model_version : str
        The resolved model version the runtime reported.
    """

    content: str = "# Drafted\n\nbody"
    model: str = "gpt-5-mini"
    output_tokens: int = 7
    model_version: str = "gpt-5-mini-2026-01"


def _assistant_event() -> SessionEvent:
    """Build a scripted ``assistant.message`` event for the happy path.

    Returns
    -------
    SessionEvent
        A structural stand-in whose ``.type`` is
        ``SessionEventType.ASSISTANT_MESSAGE`` and whose ``.data`` carries the
        fields :func:`to_draft_result` maps. Cast to ``SessionEvent`` keeps the
        strict type checker happy without constructing a full SDK event (the
        established idiom in ``tests/test_copilot_mapping.py``).
    """
    # Function-local import keeps the shared ``conftest`` itself SDK-free at
    # collection time (WR-02); only the copilot-adapter tests that actually
    # build a scripted event pull ``copilot`` into ``sys.modules``, and only
    # when this helper runs.
    from copilot import SessionEvent, SessionEventType  # noqa: PLC0415

    @dataclass
    class _Event:
        type: SessionEventType
        data: _StubAssistantData

    event = _Event(type=SessionEventType.ASSISTANT_MESSAGE, data=_StubAssistantData())
    return cast(SessionEvent, event)


class _StubSession:
    """A scripted stand-in for the SDK session returned by ``create_session``.

    Parameters
    ----------
    send_error : Exception or None
        When set, :meth:`send_and_wait` raises it instead of returning the
        scripted happy-path event — how the 03-02 error-mapping tests inject a
        fake ``JsonRpcError`` raised mid-draft.
    """

    def __init__(self, *, send_error: Exception | None = None) -> None:
        self._send_error = send_error

    async def __aenter__(self) -> _StubSession:
        """Enter the async context, returning self.

        Returns
        -------
        _StubSession
            This session, so ``async with session_cm as session`` binds it.
        """
        return self

    async def __aexit__(self, *exc: object) -> bool:
        """Exit the async context without suppressing exceptions.

        Returns
        -------
        bool
            ``False`` so any in-flight exception propagates unchanged.
        """
        return False

    async def send_and_wait(self, prompt: str, *, timeout: float) -> SessionEvent:
        """Return the scripted assistant event, or raise the scripted error.

        Parameters
        ----------
        prompt : str
            The composed drafting prompt (ignored by the stub).
        timeout : float
            The send timeout (ignored by the stub).

        Returns
        -------
        SessionEvent
            The scripted ``assistant.message`` event for the happy path.

        Raises
        ------
        Exception
            The ``send_error`` the stub was constructed with, if any.
        """
        if self._send_error is not None:
            raise self._send_error
        return _assistant_event()


class _StubClient:
    """A kwargs-capturing stand-in for ``CopilotClient``.

    Records the keyword arguments the provider passes to ``create_session`` in
    :attr:`session_kwargs` so a test can assert the model, effort, and permission
    handler the provider requested, and scripts the lifecycle so the happy path
    completes without a network call.

    Parameters
    ----------
    status_error : Exception or None
        Raised from :meth:`get_status` to simulate an unhealthy backend.
    session_error : Exception or None
        Raised from :meth:`create_session` to simulate a create-time failure
        (for example a ``JsonRpcError`` rejecting the model).
    send_error : Exception or None
        Forwarded to the scripted :class:`_StubSession` to raise from
        ``send_and_wait`` (a mid-draft failure).
    """

    def __init__(
        self,
        *,
        status_error: Exception | None = None,
        session_error: Exception | None = None,
        send_error: Exception | None = None,
    ) -> None:
        self._status_error = status_error
        self._session_error = session_error
        self._send_error = send_error
        self.session_kwargs: dict[str, object] | None = None

    async def __aenter__(self) -> _StubClient:
        """Enter the async context, returning self.

        Returns
        -------
        _StubClient
            This client, so ``async with CopilotClient() as client`` binds it.
        """
        return self

    async def __aexit__(self, *exc: object) -> bool:
        """Exit the async context without suppressing exceptions.

        Returns
        -------
        bool
            ``False`` so any in-flight exception propagates unchanged.
        """
        return False

    async def get_status(self) -> None:
        """Probe backend status, raising ``status_error`` when scripted.

        Raises
        ------
        Exception
            The ``status_error`` the stub was constructed with, if any.
        """
        if self._status_error is not None:
            raise self._status_error

    async def get_auth_status(self) -> None:
        """Probe auth status (always healthy in the stub)."""
        return None

    async def create_session(self, **kwargs: object) -> _StubSession:
        """Record the session kwargs and return a scripted session.

        Parameters
        ----------
        **kwargs : object
            The keyword arguments the provider passed (model, reasoning_effort,
            on_permission_request, available_tools, excluded_tools, ...). Stored
            on :attr:`session_kwargs` for assertion.

        Returns
        -------
        _StubSession
            The scripted session for the happy path.

        Raises
        ------
        Exception
            The ``session_error`` the stub was constructed with, if any.
        """
        self.session_kwargs = kwargs
        if self._session_error is not None:
            raise self._session_error
        return _StubSession(send_error=self._send_error)


@pytest.fixture
def install_stub_client(monkeypatch: pytest.MonkeyPatch):
    """Return a callable that injects a scripted :class:`_StubClient`.

    The returned callable builds a stub from the keyword recipe, monkeypatches
    ``dogen.adapters.copilot.provider.CopilotClient`` to a factory yielding it
    (the true SDK boundary, coding-guide §4), and returns the stub instance so
    the test can read ``session_kwargs``. ``monkeypatch`` auto-undoes the patch.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The pytest fixture used to install and auto-revert the stub.

    Returns
    -------
    callable
        ``install(*, status_error=None, session_error=None, send_error=None)``
        returning the injected ``_StubClient``.
    """

    def _install(
        *,
        status_error: Exception | None = None,
        session_error: Exception | None = None,
        send_error: Exception | None = None,
    ) -> _StubClient:
        stub = _StubClient(
            status_error=status_error,
            session_error=session_error,
            send_error=send_error,
        )

        def _factory(*_a: object, **_k: object) -> _StubClient:
            return stub

        monkeypatch.setattr(
            "dogen.adapters.copilot.provider.CopilotClient", _factory
        )
        return stub

    return _install


def _steering() -> Steering:
    """Build a minimal recorded HITL steering event for a draft.

    Returns
    -------
    Steering
        A valid steering event anchoring the draft to a human author.
    """
    return Steering(
        author="a@example.com",
        at="2026-06-20T00:00:00Z",
        intent=Intent.reference,
        audience="operators",
    )


async def _draft(provider: CopilotDraftingProvider) -> DraftResult:
    """Drive a single reference-page draft through the provider.

    Parameters
    ----------
    provider : CopilotDraftingProvider
        The provider under test (its SDK client is expected to be stubbed).

    Returns
    -------
    DraftResult
        The mapped domain result of the draft.
    """
    return await provider.draft_unit(
        intent=Intent.reference,
        audience="operators",
        steering=_steering(),
        sources=[SourceRef(path="README.md")],
    )
