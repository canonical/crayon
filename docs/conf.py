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
