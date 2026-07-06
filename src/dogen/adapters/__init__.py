"""Driven-side adapters for dogen.

Adapters are the only place external vendors and I/O specifics are wired to
the domain ports defined in :mod:`dogen.core`. Dependencies still point inward:
adapters import from the core, never the reverse. In this phase the package is
intentionally empty.
"""
