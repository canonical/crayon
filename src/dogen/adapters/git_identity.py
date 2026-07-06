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
# ``--get`` is the explicit read form (IN-02): the bare ``git config <key>``
# read form is deprecated and returns the last value for a multi-valued key,
# which is surprising for a field that becomes an immutable audit author.
_ALLOWED_COMMANDS: dict[str, list[str]] = {
    "user.name": ["git", "config", "--get", "user.name"],
    "user.email": ["git", "config", "--get", "user.email"],
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
