"""The round-3 replay end-to-end: the whole ownership lease, proven via the core API.

This is the Phase-7 acceptance gate. It replays round 3's exact failure shape
(unit B touches a page sealed by unit A) as a deterministic, core-API async mock
e2e in the ``test_loop_mock_e2e.py`` style — ``@pytest.mark.asyncio``,
``FilesystemPlanningStore()``, the deterministic ``_Clock``, and a real tmp
``repo`` fixture so the git seam writes actual commits whose ``Dogen-Extends``
trailers we read back. No CLI, no network, no Copilot SDK.

Three legs, all driven through the promoted core use-cases (declare / steer /
draft / review) via the ``dogen.app`` composition root:

* **Forward path (the round-3 failure, now green)** — A declares + seals page P;
  B declares onto A's *sealed* P and the declare commit records the supersede
  (``docs/<P> extends unit A (sealed <sha12>)`` body line + a ``Dogen-Extends: A``
  trailer); B then steers → drafts → accepts and seals P itself.
* **In-flight overlap still refuses** — declaring onto a page held by an
  in-flight (drafted, not accepted) owner raises ``TargetClaimedError`` naming
  the owner and its derived state.
* **Reverse hole closed** — A seals P; B takes it over and steers (in-flight,
  holds P); A reopens via the EXISTING ``review --verdict fix`` verb (no new
  verb), which re-arms A's lease; A's next draft hits the draft-time re-check and
  refuses because B is in-flight on P.

The scaffold (``_Clock`` / ``repo`` / ``_declare`` / ``_steer`` / ``_draft`` /
``_review`` / ``_seal``) mirrors ``tests/test_ownership_lease.py`` — the project's
per-module fixture convention (``conftest.py`` holds only the Copilot SDK stubs),
which the research sanctions copying rather than sharing.
"""

import subprocess

import pytest

from dogen.adapters.git_repo import GitRepoSeam
from dogen.adapters.planning_fs import FilesystemPlanningStore, TargetClaimedError
from dogen.app import compose
from dogen.core.models import Intent, ReviewVerdict, is_sealed
from dogen.core.orchestrator import declare, draft, review
from dogen.core.orchestrator import (
    signoff as steer,
)


def _head_message(root) -> str:
    """Return the HEAD commit's full message (subject + body + trailers)."""
    completed = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%B"],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock (no real time)."""

    def __init__(self):
        self._n = 0

    def __call__(self):
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with a configured local identity, used as the working dir.

    ``read_git_identity`` reads ``git config --get`` in the cwd, so the local
    user.name/email set here resolve deterministically with no network.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ada@example.com"],
        check=True,
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _declare(store, root, *, unit, sphinx_target=None, extra_targets=None, repo=None):  # noqa: PLR0913
    declare(
        compose.build_declare_request(
            unit,
            root=root,
            store=store,
            intent=Intent.reference,
            audience="devs",
            sphinx_target=sphinx_target,
            extra_targets=extra_targets,
            repo=repo,
        )
    )


def _steer(store, root, clock, *, unit, repo=None):
    return steer(
        compose.build_signoff_request(
            unit, root=root, store=store, now=clock, repo=repo
        )
    )


async def _draft(store, root, clock, *, unit, repo=None):
    return (
        await draft(
            compose.build_draft_request(
                unit, root=root, store=store, now=clock, repo=repo
            )
        )
    ).path


def _review(store, root, clock, note, *, unit, verdict, repo=None):  # noqa: PLR0913
    return review(
        compose.build_review_request(
            unit,
            root=root,
            store=store,
            note=note,
            now=clock,
            verdict=verdict,
            repo=repo,
        )
    )


async def _seal(store, root, clock, *, unit, sphinx_target, repo=None):  # noqa: PLR0913
    """Drive declare→steer→draft→review-accept for ``unit`` (its latest verdict
    is ``accept``, so it releases its lease on ``sphinx_target``)."""
    _declare(store, root, unit=unit, sphinx_target=sphinx_target, repo=repo)
    _steer(store, root, clock, unit=unit, repo=repo)
    await _draft(store, root, clock, unit=unit, repo=repo)
    _review(
        store,
        root,
        clock,
        "accepted",
        unit=unit,
        verdict=ReviewVerdict.accept,
        repo=repo,
    )


# --------------------------------------------------------------------------- #
# Leg 1 — the round-3 failure completes end-to-end (seal → supersede → seal)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_round3_forward_supersede_then_reseal(repo):
    # The round-3 failure shape, now green: A seals page P; B claims A's SEALED
    # page (succeeds + records the Dogen-Extends supersede on the declare commit);
    # B then seals P itself. Driven entirely through the core API with a real git
    # seam so the trailer is asserted against an actual commit.
    store = FilesystemPlanningStore()
    clock = _Clock()
    seam = GitRepoSeam()

    await _seal(store, repo, clock, unit="A", sphinx_target="guide.md", repo=seam)
    assert is_sealed(store.read_provenance("A", root=repo)) is True

    # B declares onto A's sealed page P — succeeds and records the supersede.
    _declare(store, repo, unit="B", sphinx_target="guide.md", repo=seam)
    message = _head_message(repo)
    assert "Dogen-Extends: A" in message
    assert "docs/guide.md extends unit A (sealed " in message

    # B steers → drafts (A is sealed ⇒ no in-flight conflict) → accepts ⇒ seals P.
    _steer(store, repo, clock, unit="B", repo=seam)
    await _draft(store, repo, clock, unit="B", repo=seam)
    _review(
        store,
        repo,
        clock,
        "accepted",
        unit="B",
        verdict=ReviewVerdict.accept,
        repo=seam,
    )

    prov_b = store.read_provenance("B", root=repo)
    assert is_sealed(prov_b) is True  # B now seals P — the round-3 failure closes.
    assert store.load_unit("B", root=repo).sphinx_target == "guide.md"


# --------------------------------------------------------------------------- #
# Leg 2 — in-flight overlap still refuses (the forward guard survives)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_inflight_overlap_still_refuses(repo):
    # An in-flight owner still holds its lease: C drafts (not accepted) on page P,
    # so a competing declare onto P refuses, naming C + its derived state.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo, unit="C", sphinx_target="ref.md")
    _steer(store, repo, clock, unit="C")
    await _draft(store, repo, clock, unit="C")  # in-flight: drafted, not accepted

    with pytest.raises(TargetClaimedError) as excinfo:
        _declare(store, repo, unit="D", sphinx_target="ref.md")

    message = str(excinfo.value)
    assert "C" in message
    assert "not accepted" in message


# --------------------------------------------------------------------------- #
# Leg 3 — the reverse hole: reopen a sealed unit, then the draft re-check refuses
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_reopen_then_draft_recheck_refuses(repo):
    # The reverse hole closed with NO new verb: A seals P; B takes over the sealed
    # page and steers (in-flight, holds P); A reopens via the EXISTING
    # `review --verdict fix` (which flips is_sealed back to in-flight, re-arming
    # A's lease); A's next draft hits the draft-time re-check and refuses because
    # B is in-flight on P.
    store = FilesystemPlanningStore()
    clock = _Clock()
    seam = GitRepoSeam()

    await _seal(store, repo, clock, unit="A", sphinx_target="guide.md", repo=seam)

    # B takes over A's sealed page and steers ⇒ in-flight, holds the lease on P.
    _declare(store, repo, unit="B", sphinx_target="guide.md", repo=seam)
    _steer(store, repo, clock, unit="B", repo=seam)

    # A reopens via the existing review verb — a fix verdict re-arms its lease.
    _review(
        store,
        repo,
        clock,
        "please revise",
        unit="A",
        verdict=ReviewVerdict.fix,
        repo=seam,
    )
    assert is_sealed(store.read_provenance("A", root=repo)) is False

    # A drafts again; B is in-flight on P ⇒ the draft-time re-check refuses.
    with pytest.raises(TargetClaimedError) as excinfo:
        await _draft(store, repo, clock, unit="A", repo=seam)

    message = str(excinfo.value)
    assert "B" in message
    assert "guide.md" in message
