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

"""D-08 regression guard: the private ``copilot._jsonrpc.JsonRpcError`` coupling.

The Copilot adapter (wired in plan 03-02) catches ``JsonRpcError`` to translate
a model-rejection into a handled ``ModelRejectedError``. That symbol lives at the
*private* ``copilot._jsonrpc`` path — it is not re-exported in ``copilot.__all__``
(RESEARCH Pitfall 2). A future SDK bump that moves, renames, or reshapes it would
otherwise silently drop the adapter's error catch.

The module-level import below is itself the loud signal: if the private path goes
away, collection of this module fails in CI rather than the breakage hiding until
a live run. The test additionally pins the ``code`` / ``message`` shape the
adapter reads.
"""

from copilot._jsonrpc import JsonRpcError, ProcessExitedError


def test_jsonrpc_error_is_importable_and_shaped() -> None:
    """Pin the private ``JsonRpcError`` shape the adapter relies on (D-08).

    Constructs the error with the overloaded ``-32603`` code and asserts the
    ``code`` / ``message`` attributes the adapter's error-mapping reads are
    present and carry the constructor values unchanged.
    """
    exc = JsonRpcError(-32603, "x")
    assert exc.code == -32603
    assert exc.message == "x"


def test_process_exited_error_is_importable() -> None:
    """Pin the private ``ProcessExitedError`` shape the adapter catches (D-08).

    ``provider.py`` also catches ``ProcessExitedError`` from the same private
    ``copilot._jsonrpc`` module (on both the draft and the status-probe paths).
    It is equally absent from ``copilot.__all__``, so an SDK bump that moves or
    renames it would silently drop those ``except`` handlers. Constructing it and
    asserting it is an ``Exception`` subclass guards against that — the
    module-level import is itself the loud CI signal if the private path goes
    away.
    """
    exc = ProcessExitedError("cli exited")
    assert isinstance(exc, Exception)
