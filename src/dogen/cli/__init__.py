"""Thin CLI driving adapter for dogen.

The CLI stays thin, holding no business logic and delegating into the domain
orchestration in :mod:`dogen.core`. In this phase :mod:`dogen.cli.main` exposes
a stub Typer ``app`` with no verbs; the verbs land in a later phase.
"""
