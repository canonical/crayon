"""Lane B's sandboxes: real copies of the recorded states, built once, copied per case.

Dev-time evaluation material. ``fixtures/states.sh`` builds every state in a
hermetic temp repo from ``tests/lib.sh``; with ``SNAPDIR`` set it also keeps a
copy of the repo at each ``snap`` point. ``ensure()`` runs it once per input
digest into the gitignored ``.cache/snapshots/<digest>/``, so a change to the
recorder, the fixture, the skills or ``dogen.py`` rebuilds them, and nothing
else does. ``materialise()`` copies one snapshot to a fresh temp directory for
one episode; ``discard()`` removes it.
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
    "accepted", "context_empty", "context_recorded", "context_staged", "crashed",
    "declared", "diverged", "drafted", "edited", "fixed", "missing", "no_material",
    "retired", "signed", "stale", "target_exists", "walk",
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
    paths = [RECORDER, REPO / "tests" / "lib.sh", REPO / "dogen.py"]
    for root in (HERE / "fixtures" / "toyq", REPO / "skills"):
        paths.extend(sorted(p for p in root.rglob("*") if p.is_file()))
    return paths


def digest():
    """One digest over everything that shapes a snapshot."""
    hashed = hashlib.sha256()
    for path in _inputs():
        hashed.update(str(path.relative_to(REPO)).encode("utf-8") + b"\0")
        hashed.update(path.read_bytes() + b"\0")
    return hashed.hexdigest()[:16]


def bin_dir():
    """A directory holding a ``dogen`` shim onto this checkout's ``dogen.py``."""
    directory = CACHE / "bin"
    shim = directory / "dogen"
    body = '#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, REPO / "dogen.py")
    with _LOCK:
        if not shim.is_file() or shim.read_text(encoding="utf-8") != body:
            directory.mkdir(parents=True, exist_ok=True)
            shim.write_text(body, encoding="utf-8")
            shim.chmod(0o755)
    return str(directory)


def ensure():
    """The snapshot directory for the current inputs, building it if needed."""
    target = CACHE / "snapshots" / digest()
    with _LOCK:
        if (target / ".complete").is_file():
            return target
        work = Path(tempfile.mkdtemp(prefix="dogen-snapshots-"))
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
    holder = tempfile.mkdtemp(prefix="dogen-eval-")
    repo = os.path.join(holder, "repo")
    shutil.copytree(str(source), repo, symlinks=True)
    if transform is not None:
        transform(holder, repo)
    return repo


def discard(repo):
    shutil.rmtree(os.path.dirname(os.path.realpath(repo)), ignore_errors=True)
