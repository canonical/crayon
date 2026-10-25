"""Lane B's sandboxes: real copies of the recorded states, and where commands run in them.

Dev-time evaluation material. ``fixtures/states.sh`` builds every state in a
hermetic temp repo from ``tests/lib.sh``; with ``SNAPDIR`` set it also keeps a
copy of the repo at each ``snap`` point. ``ensure()`` runs it once per input
digest into the gitignored ``.cache/snapshots/<digest>/``, so a change to the
recorder, the fixture, the skills or ``crayon.py`` rebuilds them, and nothing
else does. ``materialise()`` copies one snapshot to a fresh temp directory for
one episode; ``discard()`` removes it.

A runner carries out the episode's commands against that copy and takes its
digest (``digest.tree``):

- ``WorkshopRunner``, for a live model: a Workshop container launched from a
  staging directory under ``.cache/ws/`` that holds only the definition,
  ``crayon.py``, ``digest.py`` and the current case's copy. The copy is placed
  at ``/srv/toyq``; each command runs as ``evaluser`` (no sudo) with an
  environment built from scratch (``agent.COMMAND_ENV``). The container holds no
  secret, no host file and no eval case, and is reset before every case. Its
  network is not closed.
- ``HostRunner``, for a replay of fixed commands only (the offline self-tests
  and ``--dry-run``): the same commands on the host copy. A live model's
  commands never run on the host.

``LockPool`` lends one workshop per parallel worker, across processes.
"""

import fcntl
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import agent
import digest as treedigest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CACHE = HERE / ".cache"
RECORDER = HERE / "fixtures" / "states.sh"
DEFINITION = HERE / "workshop"
WORKSHOP = "crayon-evals"

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
    "reported",
    "reported_clean",
    "reported_noted",
    "retired",
    "signed",
    "stale",
    "target_exists",
    "triage_change",
    "tw_accepted",
    "tw_context_recorded",
    "tw_crashed",
    "tw_declared",
    "tw_diverged",
    "tw_drafted",
    "tw_missing",
    "tw_signed",
    "tw_triage_change",
    "tw_walk",
    "tw_walk_drafted",
    "walk",
    "walk_accepted",
    "walk_drafted",
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
        "validation/evals/fixtures/toyq", "validation/evals/fixtures/tidewatch", "skills/crayon-*",
    ])
    paths.extend(REPO / os.fsdecode(name) for name in tracked.split(b"\0") if name)
    return paths


def inputs_digest():
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


def ensure():
    """The snapshot directory for the current inputs, building it if needed."""
    target = CACHE / "snapshots" / inputs_digest()
    CACHE.mkdir(parents=True, exist_ok=True)
    with _LOCK, open(str(CACHE / "snapshots.lock"), "a+") as lock:
        # Several processes may ask at once (promptfoo's provider workers): one
        # builds, the others wait and then find the build complete.
        fcntl.flock(lock, fcntl.LOCK_EX)
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
    """A fresh copy of sandbox ``name``; returns the repo path inside it.

    The copy's holder directory also gets an empty ``home``, the commands'
    throwaway ``HOME``.
    """
    if name not in SANDBOXES:
        raise ValueError("no sandbox named %r" % name)
    base, transform = TRANSFORMS.get(name, (name, None))
    source = ensure() / base
    holder = tempfile.mkdtemp(prefix="crayon-eval-")
    repo = os.path.join(holder, "repo")
    shutil.copytree(str(source), repo, symlinks=True)
    os.mkdir(os.path.join(holder, "home"))
    if transform is not None:
        transform(holder, repo)
    return repo


def discard(repo):
    shutil.rmtree(os.path.dirname(os.path.realpath(repo)), ignore_errors=True)


class SandboxError(Exception):
    """The sandbox itself failed: the case is a run-level error, not a failure."""


#: Run a command, its stderr folded into its stdout as a shell tool shows it, then
#: print its exit code behind a marker the command cannot know in advance.
_WRAPPER = '( eval "$1" ) 2>&1; printf "\\n%s=%%d" "$?"'


def _split_marker(text, marker):
    head, found, code = text.rpartition("\n" + marker + "=")
    if not found or not code.strip().isdigit():
        return None
    return head, int(code.strip())


class HostRunner(object):
    """Fixed commands on the host copy: replays only, never a live model.

    The model's paths name ``agent.WORKDIR``; here they are mapped onto the copy
    and back, so a replayed command reads as it would in a workshop.
    """

    def __init__(self, timeout=agent.TIMEOUT, limit=agent.LIMIT):
        self.timeout = timeout
        self.limit = limit
        self.holder = None
        self.workdir = agent.WORKDIR

    @property
    def root(self):
        return os.path.join(self.holder, "repo")

    def reset(self, holder, workdir=agent.WORKDIR):
        self.holder = os.path.realpath(holder)
        self.workdir = workdir

    def _env(self):
        return dict(agent.COMMAND_ENV,
                    PATH="%s:/usr/local/bin:/usr/bin:/bin" % bin_dir(),
                    HOME=os.path.join(self.holder, "home"))

    def _to_disk(self, text):
        return text.replace(self.workdir, self.root)

    def _from_disk(self, text):
        return text.replace(self.root, self.workdir)

    def run(self, command):
        marker = "__crayon_rc_%s" % secrets.token_hex(8)
        argv = ["bash", "-c", _WRAPPER % marker, "bash", self._to_disk(command)]
        try:
            done = subprocess.run(argv, cwd=self.root, env=self._env(),
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return "(timed out after %ds)" % self.timeout, 124
        split = _split_marker(done.stdout.decode("utf-8", "replace"), marker)
        if split is None:
            raise SandboxError("the host shell printed no exit code")
        text, code = split
        return self._from_disk(text[: self.limit].rstrip("\n")), code

    def run_argv(self, argv):
        try:
            done = subprocess.run(argv, cwd=self.root, env=self._env(),
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return "(timed out after %ds)" % self.timeout, 124
        return self._from_disk(done.stdout.decode("utf-8", "replace")[: self.limit]), done.returncode

    def digest(self):
        return treedigest.tree(self.holder)


class WorkshopRunner(object):
    """The episode's commands in one Workshop container, as ``evaluser``.

    ``project`` is this worker's staging directory. Every call is one
    ``workshop exec`` as root that drops to ``evaluser`` with ``setpriv``
    (Workshop's own ``--uid`` needs the user to hold sudo, which ``evaluser``
    must not).
    """

    def __init__(self, project, timeout=agent.TIMEOUT, limit=agent.LIMIT):
        self.project = Path(project)
        self.timeout = timeout
        self.limit = limit
        self.workdir = agent.WORKDIR

    def _exec(self, argv, cwd=None, timeout=None):
        timeout = timeout or self.timeout
        cwd = cwd or self.workdir
        command = ["workshop", "--project", str(self.project), "exec", "-I",
                   "--uid", "0", "--gid", "0", "--cwd", cwd,
                   "--timeout", "%ds" % (timeout + 30), WORKSHOP, "--"] + argv
        try:
            done = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=timeout + 60)
        except subprocess.TimeoutExpired:
            raise SandboxError("workshop exec did not return within %ds" % (timeout + 60))
        return done

    def _as_evaluser(self, argv):
        env = ["%s=%s" % item for item in sorted(agent.COMMAND_ENV.items())]
        return (["setpriv", "--reuid=evaluser", "--regid=evaluser", "--init-groups",
                 "--reset-env", "env", "-i"] + env
                + ["timeout", "-k", "5", str(self.timeout)] + argv)

    def reset(self, holder, workdir=agent.WORKDIR):
        """Put the case's copy at ``/srv``: the repository at ``workdir``, its siblings beside it."""
        self.workdir = workdir
        case = self.project / "case"
        shutil.rmtree(str(case), ignore_errors=True)
        case.mkdir()
        for name in sorted(os.listdir(holder)):
            target = case / (os.path.basename(workdir) if name == "repo" else name)
            shutil.copytree(os.path.join(holder, name), str(target), symlinks=True)
        script = ("rm -rf /srv && mkdir /srv && cp -a /project/case/. /srv/ "
                  "&& chown -R evaluser:evaluser /srv")
        done = self._exec(["sh", "-c", script], cwd="/")
        if done.returncode != 0:
            raise SandboxError("could not reset the workshop copy: %s"
                               % done.stderr.decode("utf-8", "replace")[:300])

    def run(self, command):
        marker = "__crayon_rc_%s" % secrets.token_hex(8)
        done = self._exec(self._as_evaluser(["bash", "-c", _WRAPPER % marker, "bash", command]))
        split = _split_marker(done.stdout.decode("utf-8", "replace"), marker)
        if split is None:
            if done.returncode in (124, 137):
                return "(timed out after %ds)" % self.timeout, 124
            raise SandboxError("workshop exec failed (exit %d): %s" % (
                done.returncode, done.stderr.decode("utf-8", "replace")[:300]))
        text, code = split
        return text[: self.limit].rstrip("\n"), code

    def run_argv(self, argv):
        done = self._exec(self._as_evaluser(argv))
        if done.returncode in (124, 137):
            return "(timed out after %ds)" % self.timeout, 124
        out = (done.stdout + done.stderr).decode("utf-8", "replace")
        return out[: self.limit], done.returncode

    def digest(self):
        """The copy's digest, after every process ``evaluser`` left behind is stopped."""
        done = self._exec(["sh", "-c", "pkill -KILL -u evaluser; python3 /project/digest.py /srv"],
                          cwd="/")
        out = done.stdout.decode("utf-8", "replace").strip()
        if done.returncode != 0 or len(out) != 64:
            raise SandboxError("could not take the workshop digest: %s"
                               % done.stderr.decode("utf-8", "replace")[:300])
        return out


def _workshop_status(project):
    done = subprocess.run(["workshop", "--project", str(project), "list"],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for line in done.stdout.decode("utf-8", "replace").splitlines():
        words = line.split()
        if words and words[0] == WORKSHOP:
            return words[1] if len(words) > 1 else "unknown"
    return None


def stage(project):
    """Write a worker's staging directory: the definition, the tool and the digest script."""
    project = Path(project)
    project.mkdir(parents=True, exist_ok=True)
    target = project / ".workshop"
    if target.exists():
        shutil.rmtree(str(target))
    shutil.copytree(str(DEFINITION), str(target))
    shutil.copy2(str(REPO / "crayon.py"), str(project / "crayon.py"))
    shutil.copy2(str(HERE / "digest.py"), str(project / "digest.py"))
    (project / "case").mkdir(exist_ok=True)
    return project


def ready(project, launch=True):
    """Make the worker's workshop Ready: start it, or launch it if it was never launched.

    ``workshop list`` shows a stopped workshop and one never launched alike, as Off.
    """
    if _workshop_status(project) == "Ready":
        return
    done = subprocess.run(["workshop", "--project", str(project), "start", WORKSHOP],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    output = done.stdout.decode("utf-8", "replace")
    if done.returncode != 0 and "not launched" in output:
        if not launch:
            raise SandboxError("the %s workshop in %s was never launched" % (WORKSHOP, project))
        done = subprocess.run(["workshop", "--project", str(project), "launch", WORKSHOP],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        output = done.stdout.decode("utf-8", "replace")
    if done.returncode != 0 or _workshop_status(project) != "Ready":
        raise SandboxError("the %s workshop in %s is not Ready: %s"
                           % (WORKSHOP, project, output[-400:]))


def probe(runner):
    """The runner sees ``/srv/toyq``, runs the ``crayon`` shim and takes a digest."""
    holder = tempfile.mkdtemp(prefix="crayon-eval-probe-")
    try:
        os.mkdir(os.path.join(holder, "repo"))
        os.mkdir(os.path.join(holder, "home"))
        runner.reset(holder)
        output, code = runner.run("pwd && crayon version --json")
        if code != 0 or not output.startswith(agent.WORKDIR + "\n"):
            raise SandboxError("probe saw %r (exit %d)" % (output[:200], code))
        first = runner.digest()
        runner.run("ls -la && git status 2>/dev/null; true")
        if runner.digest() != first:
            raise SandboxError("a command that only reads changed the digest")
        json.loads(output.split("\n", 1)[1])
    finally:
        shutil.rmtree(holder, ignore_errors=True)


class LockPool(object):
    """The staged workshops shared by several processes: a case claims a free one.

    A worker is claimed by an exclusive lock on its staging directory's
    ``.busy`` file, held for the episode; promptfoo's provider processes each
    open the same pool, so no two episodes ever share a workshop.
    """

    def __init__(self, count):
        self.projects = [CACHE / "ws" / str(index) for index in range(count)]
        self.size = count

    @contextmanager
    def runner(self):
        while True:
            for project in self.projects:
                handle = open(str(project / ".busy"), "a+")
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    handle.close()
                    continue
                try:
                    yield WorkshopRunner(project)
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                    handle.close()
                return
            time.sleep(0.2)


def workers(count, launch=True):
    """Stage, launch and probe ``count`` workshops under ``.cache/ws/``; return their pool."""
    projects = [stage(CACHE / "ws" / str(index)) for index in range(count)]
    errors = []

    def bring_up(project):
        try:
            ready(project, launch=launch)
            probe(WorkshopRunner(project))
        except (SandboxError, OSError, ValueError) as exc:
            errors.append("%s: %s" % (project.name, exc))

    threads = [threading.Thread(target=bring_up, args=(project,)) for project in projects]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors:
        raise SandboxError("; ".join(errors))
    return LockPool(count)


class HostPool(object):
    """Replays only: a fresh ``HostRunner`` per case."""

    size = 1

    @contextmanager
    def runner(self):
        yield HostRunner()
