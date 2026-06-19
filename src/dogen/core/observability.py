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

"""Provider-independent observability helpers built on the OTel **API** (D-20).

This module is the instrumentation seam: ``core/`` opens spans and derives the
``run_id`` through the vendor-neutral OpenTelemetry *API* only, so OBS-01 holds
and the concrete backend (Logfire, an OTel-SDK exporter, …) stays swappable. It
imports **neither** ``logfire`` **nor** ``opentelemetry.sdk`` — that boundary is
the whole point (RESEARCH Pitfall 4 / S5) and is enforced both here and by the
import-linter contract. The backend is wired only at the CLI composition root
(:mod:`dogen.obs.logfire_backend`).

The ``run_id`` is the 32-hex OTel trace id of the active draft span; it is
stamped into ``provenance.yaml.generations[].run_id`` so the runtime trace and
the on-disk audit record line up (OBS-03/D-22).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace

_TRACER_NAME = "dogen"
_DRAFT_SPAN_NAME = "dogen.draft"

# Domain-only span attribute keys. Restricted to non-sensitive fields so no
# token/secret can leak into a trace or the local backend (threat T-02.2-03).
ATTR_UNIT_ID = "dogen.unit_id"
ATTR_INTENT = "dogen.intent"
ATTR_PROVIDER = "dogen.provider"
ATTR_RUN_ID = "dogen.run_id"


def get_tracer() -> trace.Tracer:
    """Return the dogen OTel API tracer.

    Returns
    -------
    opentelemetry.trace.Tracer
        A tracer named ``"dogen"``; a no-op tracer when no SDK provider is
        installed, so importing this module never forces a backend (OBS-01).
    """
    return trace.get_tracer(_TRACER_NAME)


def run_id_from_span(span: trace.Span) -> str:
    """Derive the 32-hex ``run_id`` from a span's trace id (OBS-03/D-22).

    Parameters
    ----------
    span : opentelemetry.trace.Span
        The active draft span.

    Returns
    -------
    str
        The span's trace id formatted as a zero-padded 32-character hex string,
        matching the W3C trace-context ``trace-id`` field the SDK propagates.
    """
    return format(span.get_span_context().trace_id, "032x")


def set_draft_attributes(
    span: trace.Span,
    *,
    unit_id: str,
    intent: str,
    provider: str,
    run_id: str,
) -> None:
    """Stamp the non-sensitive domain attributes onto a draft span.

    Only audit-relevant domain fields are recorded; no environment or token
    value is ever set as an attribute (threat T-02.2-03).

    Parameters
    ----------
    span : opentelemetry.trace.Span
        The active draft span.
    unit_id : str
        The unit being drafted.
    intent : str
        The steered Diátaxis direction.
    provider : str
        The selected provider name (``mock``/``copilot``).
    run_id : str
        The run id correlated to the provenance generation entry.
    """
    span.set_attribute(ATTR_UNIT_ID, unit_id)
    span.set_attribute(ATTR_INTENT, intent)
    span.set_attribute(ATTR_PROVIDER, provider)
    span.set_attribute(ATTR_RUN_ID, run_id)


@contextmanager
def draft_span() -> Iterator[tuple[trace.Span, str]]:
    """Open the ``dogen.draft`` span and yield it with its ``run_id``.

    Yields
    ------
    tuple of (opentelemetry.trace.Span, str)
        The active draft span and its derived 32-hex ``run_id``.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(_DRAFT_SPAN_NAME) as span:
        yield span, run_id_from_span(span)
