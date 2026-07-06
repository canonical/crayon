"""The observability composition root: concrete backend wiring.

This package is deliberately *outside* ``core/``. It is the only place a
concrete OTel backend (Logfire) is imported and configured, so the
vendor-neutral instrumentation in :mod:`dogen.core` stays free of any
``logfire`` / ``opentelemetry.sdk`` dependency. In this phase it is
intentionally empty.
"""
