"""Lane B's sandboxes: real copies of the recorded states, built once, copied per case.

Dev-time evaluation material. ``fixtures/states.sh`` builds every state in a
hermetic temp repo from ``tests/lib.sh``; with ``SNAPDIR`` set it also keeps a
copy of the repo at each ``snap`` point. ``ensure()`` runs it once per input
digest into the gitignored ``.cache/snapshots/<digest>/``, so a change to the
recorder, the fixture, the skills or ``crayon.py`` rebuilds them, and nothing
else does. ``materialise()`` copies one snapshot to a fresh temp directory for
one episode; ``discard()`` removes it. ``jail()`` is where a model's looking
commands run in that copy: a bubblewrap jail, or None where there is none.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CACHE = HERE / ".cache"
RECORDER = HERE / "fixtures" / "states.sh"

#: The ``snap`` points ``states.sh`` takes, one sandbox each. ``ensure`` checks
#: the build produced exactly these, so the two cannot drift apart silently.
SNAPSHOTS = (
    "accepted",
    "closing",
    "closing_linked",
    "closing_nested",
    "closing_walk",
    "context_empty",
    "context_recorded",
    "context_staged",
    "crashed",
    "declared",
    "diverged",
    "drafted",
    "edited",
    "fixed",
    "missing",
    "no_material",
    "retired",
    "signed",
    "stale",
    "target_exists",
    "walk",
)


def _docs_outside(holder, repo):
    """The docs root moved beside the repository and linked back into it."""
    outside = os.path.join(holder, "outside-docs")
    shutil.move(os.path.join(repo, "docs"), outside)
    os.symlink(os.path.join("..", "outside-docs"), os.path.join(repo, "docs"))


#: Sandboxes made from a snapshot at copy time, for layouts a snapshot cannot
#: hold (a link out of the repository must point somewhere that exists).
TRANSFORMS = {
    "docs_outside": ("drafted", _docs_outside),
}
SANDBOXES = SNAPSHOTS + tuple(sorted(TRANSFORMS))

_LOCK = threading.Lock()


def _inputs():
    paths = [RECORDER, REPO / "tests" / "lib.sh", REPO / "crayon.py"]
    tracked = subprocess.check_output([
        "git", "-C", str(REPO), "ls-files", "-z", "--",
        "validation/evals/fixtures/toyq", "skills/crayon-*",
    ])
    paths.extend(REPO / os.fsdecode(name) for name in tracked.split(b"\0") if name)
    return paths


def digest():
    """One digest over everything that shapes a snapshot.

    ``SNAPSHOTS`` is part of it, so naming a snapshot the recorder does not take
    rebuilds and fails in ``ensure`` rather than passing on a cached build.
    """
    hashed = hashlib.sha256(repr(SNAPSHOTS).encode("utf-8") + b"\0")
    for path in _inputs():
        hashed.update(str(path.relative_to(REPO)).encode("utf-8") + b"\0")
        hashed.update(path.read_bytes() + b"\0")
    return hashed.hexdigest()[:16]


def bin_dir():
    """A directory holding a ``crayon`` shim onto this checkout's ``crayon.py``."""
    directory = CACHE / "bin"
    shim = directory / "crayon"
    body = '#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, REPO / "crayon.py")
    with _LOCK:
        if not shim.is_file() or shim.read_text(encoding="utf-8") != body:
            directory.mkdir(parents=True, exist_ok=True)
            shim.write_text(body, encoding="utf-8")
            shim.chmod(0o755)
    return str(directory)


_JAIL = []


def jail():
    """The :class:`agent.Jail` for this machine, or None when bwrap cannot run.

    Probed once per process: a jail that starts, sees ``/srv/toyq`` and runs
    the ``crayon`` shim. A live model is never given a sandbox without one.
    """
    import agent

    with _LOCK:
        if _JAIL:
            return _JAIL[0]
        found = None
        bwrap = shutil.which("bwrap")
        if bwrap:
            directory = CACHE / "jail-bin"
            shim = directory / "crayon"
            body = '#!/bin/sh\nexec /usr/bin/python3 /opt/crayon/crayon.py "$@"\n'
            if not shim.is_file() or shim.read_text(encoding="utf-8") != body:
                directory.mkdir(parents=True, exist_ok=True)
                shim.write_text(body, encoding="utf-8")
                shim.chmod(0o755)
            candidate = agent.Jail(directory, REPO / "crayon.py", bwrap)
            holder = tempfile.mkdtemp(prefix="crayon-jail-probe-")
            try:
                os.mkdir(os.path.join(holder, "repo"))
                argv = candidate.argv(os.path.join(holder, "repo"),
                                      {"PATH": agent.Jail.PATH},
                                      "pwd && crayon version --json")
                done = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, timeout=30)
                out = done.stdout.decode("utf-8", "replace")
                if done.returncode == 0 and out.startswith(agent.WORKDIR + "\n"):
                    found = candidate
            except (OSError, subprocess.SubprocessError):
                found = None
            finally:
                shutil.rmtree(holder, ignore_errors=True)
        _JAIL.append(found)
        return found


def ensure():
    """The snapshot directory for the current inputs, building it if needed."""
    target = CACHE / "snapshots" / digest()
    with _LOCK:
        if (target / ".complete").is_file():
            return target
        work = Path(tempfile.mkdtemp(prefix="crayon-snapshots-"))
        try:
            env = dict(os.environ, SNAPDIR=str(work / "snaps"))
            (work / "snaps").mkdir()
            subprocess.run(["bash", str(RECORDER), str(work / "states.jsonl")],
                           cwd=str(REPO), env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            built = sorted(p.name for p in (work / "snaps").iterdir())
            if built != sorted(SNAPSHOTS):
                raise RuntimeError("states.sh took snapshots %s; sandbox.SNAPSHOTS names %s"
                                   % (built, sorted(SNAPSHOTS)))
            if target.exists():
                shutil.rmtree(str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(work / "snaps"), str(target))
            (target / ".complete").write_text("ok\n", encoding="utf-8")
        finally:
            shutil.rmtree(str(work), ignore_errors=True)
    return target


def materialise(name):
    """A fresh copy of sandbox ``name``; returns the repo path inside it."""
    if name not in SANDBOXES:
        raise ValueError("no sandbox named %r" % name)
    base, transform = TRANSFORMS.get(name, (name, None))
    source = ensure() / base
    holder = tempfile.mkdtemp(prefix="crayon-eval-")
    repo = os.path.join(holder, "repo")
    shutil.copytree(str(source), repo, symlinks=True)
    if transform is not None:
        transform(holder, repo)
    return repo


def discard(repo):
    shutil.rmtree(os.path.dirname(os.path.realpath(repo)), ignore_errors=True)
