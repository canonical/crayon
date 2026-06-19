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

"""The sole Logfire import site — the local OTel backend (D-21, OBS-02).

``configure_observability`` installs Logfire as the concrete OTel-SDK provider
that exports the API spans :mod:`dogen.core.observability` opens. It runs in
**local mode** (``send_to_logfire=False``): no account, no egress, no secret
leaves the host (threat T-02.2-03). This is the ONE place ``logfire`` is
imported (S5); the CLI composition root calls it once at startup, never
``core/``. The call is idempotent so repeated CLI invocations in one process
(e.g. tests) do not reconfigure the global provider.
"""

import logfire

# A single-cell mutable flag — avoids a module-level ``global`` rebind (PLW0603)
# while keeping the idempotency state private to this composition root.
_state = {"configured": False}


def configure_observability() -> None:
    """Configure the local Logfire OTel backend, once (idempotent).

    Installs Logfire in local mode (``send_to_logfire=False``) so the spans the
    core opens via the OTel API are exported locally with no network egress.
    Subsequent calls are no-ops within the same process.
    """
    if _state["configured"]:
        return
    logfire.configure(send_to_logfire=False)
    _state["configured"] = True
