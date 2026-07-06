"""The dogen composition layer.

Unlike ``dogen.core`` (pure domain logic that depends only on the port
abstractions), the ``dogen.app`` package is the wiring seam: it is *allowed* to
import ``dogen.adapters`` and ``dogen.obs`` to assemble concrete collaborators
into the core use-cases. Keeping this composition OUTSIDE ``dogen.core`` is what
lets the import-linter provider-seam contract stay green (Pitfall 6): the core
never sees an adapter, a logfire, or an SDK import, so a later backend swap does
not touch the domain.
"""
