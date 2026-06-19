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

"""The observability composition root: concrete backend wiring (D-21).

This package is deliberately *outside* ``core/``. It is the only place a
concrete OTel backend (Logfire) is imported and configured, so the
vendor-neutral instrumentation in :mod:`dogen.core.observability` stays free of
any ``logfire`` / ``opentelemetry.sdk`` dependency (OBS-01 / S5). The CLI calls
:func:`dogen.obs.logfire_backend.configure_observability` once at startup.
"""
