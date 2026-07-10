"""dogen: an agentic documentation-drafting framework.

The package root for the src-layout ``dogen`` distribution. It exposes the
hexagonal layout (``core``, ``adapters``, ``cli``) and carries the package
version marker. Provenance records now stamp the real installed version via
``orchestrator.tooling_version()`` (``importlib.metadata``); this constant
remains the honest fallback string and is still read by ``skills_install.py``.
"""

__version__ = "0.0.0"
