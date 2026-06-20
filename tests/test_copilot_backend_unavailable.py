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

"""Backend-unavailable handling + the structural port check (no live SDK).

A stubbed ``CopilotClient`` injected into the provider module simulates the
backend being down/unauthenticated (``StopError`` from ``get_status``) or the
transport failing on ``__aenter__`` (issue #1606). The provider must surface a
handled ``BackendUnavailableError`` with a clear message — never an uncaught
crash (SKEL-05/D-27). No network/SDK call occurs: pytest only touches stubs.

Also asserts ``CopilotDraftingProvider`` structurally satisfies the shared
``core.ports.DraftingProvider`` port (the smoke harness's non-live branch lives
in :mod:`tests.test_smoke_harness`).
"""

import pytest
from copilot import StopError

from dogen.adapters.copilot.provider import (
    BackendUnavailableError,
    CopilotDraftingProvider,
)
from dogen.core.models import Effort, Intent, SourceRef, Steering
from dogen.core.ports import DraftingProvider


def _steering() -> Steering:
    return Steering(
        author="a@example.com",
        at="2026-06-20T00:00:00Z",
        intent=Intent.reference,
        audience="operators",
    )


async def _draft(provider: CopilotDraftingProvider):
    return await provider.draft_unit(
        intent=Intent.reference,
        audience="operators",
        steering=_steering(),
        sources=[SourceRef(path="README.md")],
    )


class _StubClient:
    """A stand-in CopilotClient whose lifecycle/status is scripted by a recipe."""

    def __init__(
        self, *, enter_error: Exception | None, status_error: Exception | None
    ) -> None:
        self._enter_error = enter_error
        self._status_error = status_error

    async def __aenter__(self) -> "_StubClient":
        if self._enter_error is not None:
            raise self._enter_error
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get_status(self) -> None:
        if self._status_error is not None:
            raise self._status_error

    async def get_auth_status(self) -> None:
        return None


def _install_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enter_error: Exception | None,
    status_error: Exception | None,
) -> None:
    """Replace the provider module's CopilotClient with a stub factory."""

    def _factory(*_a: object, **_k: object) -> _StubClient:
        return _StubClient(enter_error=enter_error, status_error=status_error)

    monkeypatch.setattr("dogen.adapters.copilot.provider.CopilotClient", _factory)


def test_provider_satisfies_drafting_port() -> None:
    provider = CopilotDraftingProvider()
    # Structural (runtime_checkable Protocol) — the orchestrator drives it unchanged.
    assert isinstance(provider, DraftingProvider)
    assert hasattr(provider, "draft_unit")


@pytest.mark.asyncio
async def test_stop_error_from_status_becomes_handled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_stub(monkeypatch, enter_error=None, status_error=StopError("cli stopped"))
    provider = CopilotDraftingProvider()

    with pytest.raises(BackendUnavailableError) as excinfo:
        await _draft(provider)
    assert "status check failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_connection_failure_on_enter_becomes_handled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_stub(
        monkeypatch,
        enter_error=ConnectionError("transport broken (#1606)"),
        status_error=None,
    )
    provider = CopilotDraftingProvider()

    with pytest.raises(BackendUnavailableError) as excinfo:
        await _draft(provider)
    assert "unavailable" in str(excinfo.value)


def test_effort_maps_to_sdk_literal() -> None:
    # The domain Effort enum (incl. xhigh) maps to the SDK reasoning_effort
    # Literal without leaking an SDK type into the constructor surface.
    provider = CopilotDraftingProvider(effort=Effort.xhigh)
    assert provider._effort.value == "xhigh"
