"""The §D4 model-identity milestone slice, proven end-to-end via the core API.

This is the Phase-8 acceptance gate for the model-identity beats of the
milestone verification (v1.1-DESIGN §"Milestone verification" #2). It replays the
round-3 failure classes — a forgotten model stamped by a *duplicate generation*,
and an *unsteered redraft* fired by a byte-identical re-run — and proves both are
now structurally impossible, as a deterministic core-API async mock e2e in the
``test_ownership_lease_e2e.py`` style: ``@pytest.mark.asyncio``,
``FilesystemPlanningStore()``, the deterministic ``_Clock``, and a real tmp
``repo`` fixture so the git seam writes actual commits whose ``Dogen-Phase`` /
``Dogen-Model`` trailers we read back. No CLI, no network, no Copilot SDK.

Two beats, both driven through the promoted core use-cases (declare / steer /
draft / review / amend) via the ``dogen.app`` composition root and a real
``GitRepoSeam``:

* **Missing model -> amend (no new generation)** — a passenger drafts with the
  host hiding its model (``model_unrecorded``), the unit is then *accepted*
  (sealed), and ``amend_model`` fills the forgotten model on the already-sealed
  unit: exactly one ``model-amended`` commit, ``len(generations)`` unchanged, and
  ``is_sealed`` / ``derive_progress`` untouched — never a duplicate generation.
* **Byte-identical redraft (no warning)** — re-drafting the same bytes is a true
  no-op: no new generation, no commit, ``identical_draft`` True, and no
  ``unsteered_redraft`` signal.

The scaffold (``_Clock`` / ``repo`` / ``_declare`` / ``_steer`` / ``_draft`` /
``_review`` / ``_amend``) mirrors ``tests/test_ownership_lease_e2e.py`` — the
project's per-module fixture convention (``conftest.py`` holds only the Copilot
SDK stubs), which the research sanctions copying rather than sharing.
"""

import subprocess

import pytest

from dogen.adapters.git_repo import GitRepoSeam
from dogen.adapters.host_harness import HostHarnessDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
from dogen.core.models import Intent, ReviewVerdict, derive_progress, is_sealed
from dogen.core.orchestrator import amend_model, declare, draft, review
from dogen.core.orchestrator import signoff as steer


def _head_message(root) -> str:
    """Return the HEAD commit's full message (subject + body + trailers)."""
    completed = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%B"],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _commit_count(root) -> int:
    """Count the commits on HEAD (0 before the first commit exists)."""
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-list", "--count", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return int(completed.stdout.strip()) if completed.returncode == 0 else 0


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
    ``DOGEN_MODEL`` is cleared so an ambient env pin never overrides the empty
    resolution the missing-model beat depends on.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ada@example.com"],
        check=True,
    )
    monkeypatch.delenv("DOGEN_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _declare(store, root, *, unit, sphinx_target="guide.md", repo=None):
    declare(
        compose.build_declare_request(
            unit,
            root=root,
            store=store,
            intent=Intent.reference,
            audience="devs",
            sphinx_target=sphinx_target,
            repo=repo,
        )
    )


def _steer(store, root, clock, *, unit, repo=None):
    return steer(
        compose.build_signoff_request(
            unit, root=root, store=store, now=clock, repo=repo
        )
    )


async def _draft(store, root, clock, *, unit, provider=None, repo=None):  # noqa: PLR0913
    return await draft(
        compose.build_draft_request(
            unit,
            root=root,
            store=store,
            now=clock,
            provider=provider,
            repo=repo,
        )
    )


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


def _amend(store, root, *, unit, name, origin, repo=None):  # noqa: PLR0913
    return amend_model(store, unit, name=name, origin=origin, root=root, repo=repo)


# --------------------------------------------------------------------------- #
# Beat 1 — missing model -> amend on a SEALED unit (never a new generation)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_missing_model_then_amend_records_no_new_generation(repo):
    # The round-3 recovery, end-to-end: a passenger drafts with the host hiding
    # its model (model_unrecorded), the unit is accepted (sealed), then the
    # forgotten model is amended in place — exactly one model-amended commit, NO
    # new generation, and the seal + derived progress are untouched. Driven
    # through the real core API with a real git seam so the trailer is asserted
    # against an actual commit.
    store = FilesystemPlanningStore()
    clock = _Clock()
    seam = GitRepoSeam()

    _declare(store, repo, unit="u", repo=seam)
    _steer(store, repo, clock, unit="u", repo=seam)
    # Passenger draft with the host asserting NO model -> the generation records
    # an empty model slot (the exact "forgotten model" shape).
    passenger = HostHarnessDraftingProvider(draft_text="# host page\n", model="")
    outcome = await _draft(store, repo, clock, unit="u", provider=passenger, repo=seam)
    assert outcome.model_unrecorded is True

    # Accept -> the unit seals (it released its lease); the model is still empty.
    _review(
        store,
        repo,
        clock,
        "accepted",
        unit="u",
        verdict=ReviewVerdict.accept,
        repo=seam,
    )
    prov_before = store.read_provenance("u", root=repo)
    assert prov_before.generations[-1].model == ""
    assert is_sealed(prov_before) is True
    gens_before = len(prov_before.generations)
    sealed_before = is_sealed(prov_before)
    progress_before = derive_progress(prov_before)
    commits_before = _commit_count(repo)

    # Amend the forgotten model on the already-sealed unit.
    _amend(store, repo, unit="u", name="gpt-4o", origin="ta", repo=seam)

    prov_after = store.read_provenance("u", root=repo)
    # NO new generation — the round-3 duplicate-generation class is impossible.
    assert len(prov_after.generations) == gens_before
    assert prov_after.generations[-1].model == "gpt-4o"
    assert prov_after.generations[-1].model_origin == "ta"
    # Exactly ONE additional commit, and it is the model-amended transition.
    assert _commit_count(repo) == commits_before + 1
    message = _head_message(repo)
    assert "Dogen-Phase: model-amended" in message
    assert "Dogen-Model: gpt-4o" in message
    # The seal and derived progress are structurally untouched (no reopen).
    assert is_sealed(prov_after) is True
    assert is_sealed(prov_after) == sealed_before
    assert derive_progress(prov_after) == progress_before


# --------------------------------------------------------------------------- #
# Beat 2 — a byte-identical redraft is a true no-op (no warning, no generation)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_byte_identical_redraft_is_a_true_no_op(repo):
    # The unsteered-redraft failure class, end-to-end: the deterministic mock
    # repeats its bytes for the same unit inputs, so a redraft is byte-identical
    # -> a TRUE no-op. No new generation, no new commit, identical_draft True,
    # and NO unsteered_redraft signal (the model-stamp path is an amend, never a
    # re-run). Driven through the real core API + a real git seam.
    store = FilesystemPlanningStore()
    clock = _Clock()
    seam = GitRepoSeam()

    _declare(store, repo, unit="u", repo=seam)
    _steer(store, repo, clock, unit="u", repo=seam)
    await _draft(store, repo, clock, unit="u", repo=seam)  # first (mock) draft

    gens_before = len(store.read_provenance("u", root=repo).generations)
    commits_before = _commit_count(repo)

    # Re-draft the SAME bytes (the mock is deterministic for the same unit).
    outcome = await _draft(store, repo, clock, unit="u", repo=seam)

    assert outcome.identical_draft is True
    assert outcome.unsteered_redraft is False
    assert len(store.read_provenance("u", root=repo).generations) == gens_before
    assert _commit_count(repo) == commits_before  # no new commit — a true no-op
