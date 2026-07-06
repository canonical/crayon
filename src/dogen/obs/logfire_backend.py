"""The sole Logfire import site — the local OTel backend (D-21, OBS-02).

``configure_observability`` installs Logfire as the concrete OTel-SDK provider
that exports the API spans :mod:`dogen.core.observability` opens. It runs in
**local mode** (``send_to_logfire=False``): no account, no egress, no secret
leaves the host (threat T-02.2-03). This is the ONE place ``logfire`` is
imported (S5); the CLI composition root calls it once at startup, never
``core/``. The call is idempotent so repeated CLI invocations in one process
(e.g. tests) do not reconfigure the global provider.

The console span export is routed to **stderr** (not the default stdout) so the
CLI's own stdout carries only its result surface — the plain success line or, for
``dogen draft --json``, a single clean JSON object the Phase-4 skills parse (D-08).
Span telemetry stays visible to humans on stderr without corrupting the
machine-readable seam.
"""

import sys

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
    logfire.configure(
        send_to_logfire=False,
        console=logfire.ConsoleOptions(output=sys.stderr),
    )
    _state["configured"] = True
