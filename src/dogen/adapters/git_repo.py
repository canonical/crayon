"""Version stamps and transition commits behind a tiny git adapter (the seam).

This is the single place plumbing git commands for the v1 commit seam are
shelled, mirroring :mod:`dogen.adapters.git_identity`'s posture: fixed argument
vectors only — never arbitrary shell, never string interpolation of user input
into a command line (coding-guide §5; threat T-02.1-02). Paths and the commit
message travel as discrete ``argv`` elements. The subprocess runner is
injectable so tests stub the host boundary and stay deterministic.

The adapter implements :class:`dogen.core.ports.RepoSeam`. It is deliberately
tolerant of two benign states — *not a git repository* and *nothing to
commit* — both of which return ``""`` rather than raising, so the drafting
loop keeps working in a bare directory (the stamps simply stay empty and the
operator can see the inactive seam via ``dogen status``). Real git failures
(for example an unconfigured identity at commit time) raise
:class:`GitRepoError` with the underlying message.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

#: A runner takes one fixed argument vector and returns ``(exit_code, stdout,
#: stderr)``. Injectable so tests never shell out.
GitRunner = Callable[[list[str]], tuple[int, str, str]]

#: The stderr/stdout signature git prints outside a work tree — the benign
#: "not a repository" state the seam treats as inactive rather than an error.
_NOT_A_REPO_SIGNATURE = "not a git repository"


class GitRepoError(RuntimeError):
    """Raised when a commit-seam git operation fails for a real reason.

    "Not a repository" and "nothing to commit" are *not* real reasons — both
    are handled states returning ``""`` — so this surfaces only genuine
    failures (unconfigured identity, corrupt index, …) the operator must see.
    """


def _default_runner(args: list[str]) -> tuple[int, str, str]:
    """Run one fixed git argument vector and return its outcome.

    Parameters
    ----------
    args : list of str
        The complete argument vector (``["git", "-C", <root>, ...]``).

    Returns
    -------
    tuple of (int, str, str)
        The exit code, stripped stdout, and stripped stderr.
    """
    completed = subprocess.run(args, capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


class GitRepoSeam:
    """The concrete :class:`~dogen.core.ports.RepoSeam` over local git.

    Parameters
    ----------
    runner : GitRunner, optional
        Callable executing a fixed git argument vector; defaults to a real
        subprocess. Tests inject a stub.
    """

    def __init__(self, *, runner: GitRunner = _default_runner) -> None:
        self._run = runner

    def head_commit(self, *, root: Path) -> str:
        """Return the repo's current HEAD commit hash, or ``""``.

        Parameters
        ----------
        root : Path
            The repo root.

        Returns
        -------
        str
            The full HEAD hash; ``""`` when ``root`` is not a git repository
            or has no commits yet (both benign for stamping).
        """
        code, out, _err = self._run(["git", "-C", str(root), "rev-parse", "HEAD"])
        return out if code == 0 else ""

    def tracked(self, *, root: Path, paths: list[str]) -> set[str]:
        """Return the subset of ``paths`` with tracked content, or ``set()``.

        One batch ``git ls-files -z`` call; each output file is mapped back to
        the input path it matched (equality, or containment for directory
        paths), so directory sources like ``docs/`` count as tracked when any
        tracked file lives beneath them.

        Parameters
        ----------
        root : Path
            The repo root.
        paths : list of str
            Repo-relative candidate paths (files or directories).

        Returns
        -------
        set of str
            The tracked members of ``paths``; empty when ``root`` is not a
            git repository (benign, mirrors :meth:`head_commit`).
        """
        if not paths:
            return set()
        code, out, _err = self._run(
            ["git", "-C", str(root), "ls-files", "-z", "--", *paths]
        )
        if code != 0 or not out:
            return set()
        tracked_files = [f for f in out.split("\0") if f]
        hits: set[str] = set()
        for candidate in paths:
            prefix = candidate.rstrip("/") + "/"
            for tracked_file in tracked_files:
                if tracked_file == candidate or tracked_file.startswith(prefix):
                    hits.add(candidate)
                    break
        return hits

    def commit(self, *, root: Path, paths: list[Path], message: str) -> str:
        """Stage the given paths and record one local transition commit.

        The pathspec limits both the staging and the commit to dogen's own
        artifacts (and the draft), so unrelated operator-staged work is never
        swept into a seam commit. Deletions under the paths (``unit rm``) are
        captured by ``add -A``.

        Parameters
        ----------
        root : Path
            The repo root.
        paths : list of Path
            The paths to stage and commit.
        message : str
            The full commit message including the ``Dogen-*`` trailers.

        Returns
        -------
        str
            The new commit's hash; ``""`` when the directory is not a git
            repository or the paths held no changes (both benign no-ops).

        Raises
        ------
        GitRepoError
            On a genuine git failure (for example an unconfigured identity).
        """
        if not paths:
            return ""
        spec = [str(p) for p in paths]
        code, _out, err = self._run(["git", "-C", str(root), "add", "-A", "--", *spec])
        if code != 0:
            if _NOT_A_REPO_SIGNATURE in err.lower():
                return ""
            raise GitRepoError(f"git add failed: {err}")
        code, out, err = self._run(
            ["git", "-C", str(root), "status", "--porcelain", "--", *spec]
        )
        if code != 0:
            raise GitRepoError(f"git status failed: {err}")
        if not out:
            return ""
        code, out, err = self._run(
            ["git", "-C", str(root), "commit", "-m", message, "--", *spec]
        )
        if code != 0:
            raise GitRepoError(f"git commit failed: {err or out}")
        return self.head_commit(root=root)
