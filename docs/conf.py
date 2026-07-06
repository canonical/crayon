"""Sphinx configuration for the dogen documentation set.

The drafted MyST pages under ``docs/`` are the dogfood proof that the loop's
output is genuinely Sphinx-publishable. ``myst_parser`` MUST be in ``extensions``
or Sphinx will not parse the ``.md`` pages as MyST (RESEARCH Pitfall 6) and a
``-W`` build would "pass" without proving anything. ``colon_fence`` lets the
drafted prose use ``:::`` directive fences, which models emit far more reliably
than rST's whitespace-strict syntax.
"""

project = "dogen"
author = "Canonical Ltd."
copyright = "2026 Canonical Ltd."  # noqa: A001

# MyST parsing is what makes the .md pages publishable; without this extension
# the build is a no-op proof (RESEARCH Pitfall 6).
extensions = ["myst_parser"]

# `colon_fence` enables ::: fenced directives in MyST (the model-friendly form).
myst_enable_extensions = ["colon_fence"]

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

# Clean, responsive theme for local HTML review; RTD can re-theme if desired.
html_theme = "furo"

# Generated build output, not source — never committed (gitignored).
exclude_patterns = ["_build"]
