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

"""The kwargs the provider hands ``create_session`` (LIVE-02/LIVE-03, no network).

These tests drive a single draft through :class:`CopilotDraftingProvider` against
the shared kwargs-capturing ``_StubClient`` (``tests/conftest.py``) and assert the
keyword arguments the provider passed to ``create_session``:

* the read-only permission handler is wired so non-interactive source reads are
  auto-approved (LIVE-02 — ``on_permission_request is PermissionHandler.approve_all``);
* ``reasoning_effort`` is sent for a GPT-5-family model and omitted (``None``) for a
  Claude-family model, so Claude drafts no longer error on the parameter (LIVE-03).

No live SDK call or network access occurs: pytest only touches the stubs.
"""

import pytest
from copilot.session import PermissionHandler

from dogen.adapters.copilot.provider import CopilotDraftingProvider
from tests.conftest import _draft


@pytest.mark.asyncio
async def test_create_session_wires_approve_all_permission_handler(
    install_stub_client,
) -> None:
    """LIVE-02: ``create_session`` receives ``PermissionHandler.approve_all``.

    The staticmethod reference itself must be passed (not called), so the SDK's
    ``bool(on_permission_request)`` gate is satisfied and read-only source
    lookups are auto-approved on a non-interactive run.
    """
    stub = install_stub_client()
    await _draft(CopilotDraftingProvider())

    assert stub.session_kwargs is not None
    assert (
        stub.session_kwargs["on_permission_request"] is PermissionHandler.approve_all
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "expected_effort"),
    [
        ("gpt-5-mini", "medium"),
        ("gpt-5", "medium"),
        ("claude-sonnet-4.5", None),
        ("claude-haiku-4.5", None),
    ],
)
async def test_reasoning_effort_is_family_gated(
    install_stub_client, model: str, expected_effort: str | None
) -> None:
    """LIVE-03: ``reasoning_effort`` only for GPT-5-family, ``None`` otherwise.

    The SDK omits a falsy ``reasoning_effort`` from the wire, so passing ``None``
    for a Claude-family model is the clean implementation of the family gate.
    """
    stub = install_stub_client()
    await _draft(CopilotDraftingProvider(model=model))

    assert stub.session_kwargs is not None
    assert stub.session_kwargs.get("reasoning_effort") == expected_effort
