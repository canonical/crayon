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

"""Capture the committing author's git identity behind a tiny adapter (D-41).

This is the single place ``git config`` is shelled, and it uses an explicit
command allowlist — never arbitrary shell, never string interpolation of user
input (coding-guide §5; threat T-02.1-02). The subprocess runner is injectable
so tests stub the host boundary and stay deterministic (coding-guide §4).
"""

import subprocess
from collections.abc import Callable

# The only git invocations this adapter may issue. Nothing else is shelled, and
# no user input is interpolated into these argument lists (T-02.1-02).
_ALLOWED_COMMANDS: dict[str, list[str]] = {
    "user.name": ["git", "config", "user.name"],
    "user.email": ["git", "config", "user.email"],
}

GitConfigRunner = Callable[[list[str]], str]


class GitIdentityError(RuntimeError):
    """Raised when the git identity (name or email) is not configured."""


def _default_runner(args: list[str]) -> str:
    """Run an allowlisted git command and return its trimmed stdout.

    Parameters
    ----------
    args : list of str
        One of the allowlisted argument vectors from :data:`_ALLOWED_COMMANDS`.

    Returns
    -------
    str
        The command's stdout with surrounding whitespace stripped, or an empty
        string if git exits nonzero (e.g. the key is unset).
    """
    completed = subprocess.run(args, capture_output=True, text=True, check=False)
    return completed.stdout.strip()


def read_git_identity(*, runner: GitConfigRunner = _default_runner) -> tuple[str, str]:
    """Return the configured git ``user.name`` and ``user.email``.

    Parameters
    ----------
    runner : GitConfigRunner, optional
        Callable executing an allowlisted git argument vector and returning its
        stdout. Defaults to a real subprocess; tests inject a stub.

    Returns
    -------
    tuple of (str, str)
        The configured ``(name, email)``.

    Raises
    ------
    GitIdentityError
        If either ``user.name`` or ``user.email`` is unset.
    """
    name = runner(_ALLOWED_COMMANDS["user.name"])
    email = runner(_ALLOWED_COMMANDS["user.email"])
    if not name or not email:
        raise GitIdentityError(
            "git identity is not configured; set user.name and user.email"
        )
    return name, email
