"""Ownership-lease derivations and multi-owner resolution (Phase 7, Wave 0).

The shared test scaffold every later Phase-7 plan reuses. It carries the
module-local ``_Clock`` + ``repo`` fixtures (the project convention is
per-module fixtures — ``conftest.py`` holds only the Copilot SDK stubs) and a
reusable ``_seal(...)`` helper (declare→steer→draft→review-accept) that stands
up a sealed neighbour on disk.

Two pure, zero-I/O derivations live in :mod:`dogen.core.models` next to
``derive_progress``: ``is_sealed`` (the lease boundary, D-01/D-03) and
``_latest_accept_at`` (the D-04 ordering key). One resolver lives in
:mod:`dogen.core.orchestrator`: ``resolve_owners`` (in-flight first, else
newest-accept, tie by unit id), with ``find_unit_by_draft`` reduced to a thin
winner-only wrapper over it. The ``_scan_load_provenance`` loader tolerates a
corrupt/schema-newer neighbour (WR-01): it skips, warns, and never crashes.
"""

import hashlib
import subprocess

import pytest

from dogen.adapters.git_repo import GitRepoSeam
from dogen.adapters.planning_fs import FilesystemPlanningStore, TargetClaimedError
from dogen.app import compose
from dogen.core.models import (
    FileDigest,
    Intent,
    Provenance,
    ReviewerEdit,
    ReviewVerdict,
    Takeover,
    _latest_accept_at,
    is_sealed,
)
from dogen.core.orchestrator import (
    OwnerRef,
    ResolvedOwners,
    declare,
    draft,
    edit_unit,
    find_unit_by_draft,
    resolve_owners,
    review,
)
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


def _declare(  # noqa: PLR0913
    store, root, *, unit="u", sphinx_target=None, extra_targets=None, repo=None
):
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


def _steer(store, root, clock, *, unit="u", force=False, repo=None):
    return steer(
        compose.build_signoff_request(
            unit, root=root, store=store, now=clock, force=force, repo=repo
        )
    )


async def _draft(store, root, clock, *, unit="u", repo=None):
    return (
        await draft(
            compose.build_draft_request(
                unit, root=root, store=store, now=clock, repo=repo
            )
        )
    ).path


def _review(  # noqa: PLR0913
    store, root, clock, note, *, unit="u", verdict=ReviewVerdict.fix, repo=None
):
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


async def _seal(  # noqa: PLR0913
    store, root, clock, *, unit="A", sphinx_target=None, extra_targets=None, repo=None
):
    """Drive declare→steer→draft→review-accept for ``unit`` and return its id.

    The shared fixture later waves reuse to stand up a sealed neighbour on
    disk: the unit's latest verdict is ``accept`` (D-01), so it releases its
    lease on the pages in ``unit.targets``. Pass ``repo`` to record real seam
    commits (needed by the takeover-trailer integration tests).
    """
    _declare(
        store,
        root,
        unit=unit,
        sphinx_target=sphinx_target,
        extra_targets=extra_targets,
        repo=repo,
    )
    _steer(store, root, clock, unit=unit, repo=repo)
    await _draft(store, root, clock, unit=unit, repo=repo)
    _review(
        store, root, clock, "accepted", unit=unit, verdict=ReviewVerdict.accept, repo=repo
    )
    return unit


def _edit(at, *, verdict=None, summary="note"):
    """Build a bare ``ReviewerEdit`` with the given timestamp/verdict (no repo)."""
    return ReviewerEdit(at=at, reviewer="Ada", summary=summary, verdict=verdict)


# --------------------------------------------------------------------------- #
# Task 1 — is_sealed / _latest_accept_at pure derivations (D-01/D-03/D-04)
# --------------------------------------------------------------------------- #


def test_is_sealed_no_verdict():
    # D-03: an empty reviewer_edits history is in-flight — it holds its lease.
    prov = Provenance(unit_id="A")
    assert is_sealed(prov) is False


def test_is_sealed_accept():
    # D-01: the latest verdict-bearing edit is accept ⇒ sealed.
    prov = Provenance(
        unit_id="A",
        reviewer_edits=[
            _edit("2026-01-01T00:00:01Z", verdict=ReviewVerdict.fix),
            _edit("2026-01-01T00:00:02Z", verdict=ReviewVerdict.accept),
        ],
    )
    assert is_sealed(prov) is True


def test_is_sealed_trailing_note():
    # D-01: a non-verdict note appended AFTER an accept must not re-open the
    # lease — the backward scan stops at the first verdict-bearing entry.
    prov = Provenance(
        unit_id="A",
        reviewer_edits=[
            _edit("2026-01-01T00:00:01Z", verdict=ReviewVerdict.accept),
            _edit("2026-01-01T00:00:02Z", verdict=None, summary="drive-by note"),
        ],
    )
    assert is_sealed(prov) is True


def test_is_sealed_fix_pending():
    # D-03: the latest verdict is fix (or redraft) ⇒ in-flight, holds its lease.
    prov_fix = Provenance(
        unit_id="A",
        reviewer_edits=[
            _edit("2026-01-01T00:00:01Z", verdict=ReviewVerdict.accept),
            _edit("2026-01-01T00:00:02Z", verdict=ReviewVerdict.fix),
        ],
    )
    prov_redraft = Provenance(
        unit_id="A",
        reviewer_edits=[_edit("2026-01-01T00:00:01Z", verdict=ReviewVerdict.redraft)],
    )
    assert is_sealed(prov_fix) is False
    assert is_sealed(prov_redraft) is False


def test_latest_accept_at_normalizes_forms():
    # D-04: accepts stored with a `Z` suffix and with `+00:00` both parse to
    # aware datetimes and order correctly; None when no accept exists.
    prov_z = Provenance(
        unit_id="A",
        reviewer_edits=[_edit("2026-01-01T00:00:01Z", verdict=ReviewVerdict.accept)],
    )
    prov_offset = Provenance(
        unit_id="B",
        reviewer_edits=[
            _edit("2026-01-01T00:00:02+00:00", verdict=ReviewVerdict.accept)
        ],
    )
    prov_none = Provenance(
        unit_id="C",
        reviewer_edits=[_edit("2026-01-01T00:00:03Z", verdict=ReviewVerdict.fix)],
    )

    at_z = _latest_accept_at(prov_z)
    at_offset = _latest_accept_at(prov_offset)

    assert at_z is not None and at_z.tzinfo is not None
    assert at_offset is not None and at_offset.tzinfo is not None
    # Both normalize to aware UTC datetimes that compare without a TypeError.
    assert at_z < at_offset
    assert _latest_accept_at(prov_none) is None
    assert _latest_accept_at(Provenance(unit_id="D")) is None


# --------------------------------------------------------------------------- #
# Task 2 — resolve_owners multi-owner resolver + WR-01-tolerant scan loader
# --------------------------------------------------------------------------- #
#
# The declare/edit overlap guard (`_assert_targets_unclaimed`) still refuses ANY
# overlap in this plan — its sealed-vs-in-flight split is a later Phase-7 wave.
# So multi-owner fixtures are planted directly on disk (unit.md + provenance),
# bypassing that guard, to exercise `resolve_owners` in isolation.


def _plant_unit(store, root, unit_id, *, targets):
    """Write a unit.md pointing at ``targets`` (bypasses the declare guard)."""
    primary, *extras = targets
    md_path = store._unit_md_path(unit_id, root=root)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        store._render_unit_md(
            unit_id,
            intent=Intent.reference,
            audience="devs",
            sphinx_target=primary,
            extra_targets=extras or None,
        ),
        encoding="utf-8",
    )
    return md_path


def _plant_accept(store, root, unit_id, at):
    """Plant a sealed provenance (latest verdict ``accept`` at ``at``)."""
    store.write_provenance(
        Provenance(
            unit_id=unit_id,
            reviewer_edits=[_edit(at, verdict=ReviewVerdict.accept)],
        ),
        root=root,
    )


def _plant_corrupt(store, root, unit_id):
    """Plant a schema-newer provenance.yaml (read raises SchemaUnsupportedError)."""
    md_path = store._unit_md_path(unit_id, root=root)
    (md_path.parent / "provenance.yaml").write_text(
        f"schema_version: 999\nunit_id: {unit_id}\n", encoding="utf-8"
    )


def test_resolve_prefers_inflight(repo):
    # A page covered by one in-flight owner and one sealed owner ⇒ the in-flight
    # owner wins (it still holds its lease).
    store = FilesystemPlanningStore()
    _plant_unit(store, repo, "A", targets=["p.md"])
    _plant_accept(store, repo, "A", "2026-01-01T00:00:01Z")  # sealed
    _plant_unit(store, repo, "X", targets=["p.md"])  # in-flight (no provenance)
    request = compose.build_list_request(root=repo, store=store)

    resolved = resolve_owners(request, "p.md")

    assert resolved.winner_id == "X"
    assert {o.unit_id for o in resolved.owners} == {"A", "X"}


def test_resolve_newest_accept(repo):
    # Among sealed owners the newest accept wins across mixed Z/+00:00 forms;
    # a same-timestamp tie is broken deterministically by unit id (smallest).
    store = FilesystemPlanningStore()
    _plant_unit(store, repo, "A", targets=["p.md"])
    _plant_accept(store, repo, "A", "2026-01-01T00:00:01Z")  # older, Z form
    _plant_unit(store, repo, "B", targets=["p.md"])
    _plant_accept(store, repo, "B", "2026-01-01T00:00:05+00:00")  # newer, offset form
    request = compose.build_list_request(root=repo, store=store)

    assert resolve_owners(request, "p.md").winner_id == "B"

    # Tie: identical accept timestamps (one Z, one +00:00) ⇒ smallest unit id.
    _plant_unit(store, repo, "C", targets=["q.md"])
    _plant_accept(store, repo, "C", "2026-02-02T00:00:00Z")
    _plant_unit(store, repo, "D", targets=["q.md"])
    _plant_accept(store, repo, "D", "2026-02-02T00:00:00+00:00")

    assert resolve_owners(request, "q.md").winner_id == "C"


def test_resolve_owners_lists_all(repo):
    # resolve_owners lists every covering owner with its sealed flag + accept_at,
    # and find_unit_by_draft is the thin winner-only wrapper over it.
    store = FilesystemPlanningStore()
    _plant_unit(store, repo, "A", targets=["p.md"])
    _plant_accept(store, repo, "A", "2026-01-01T00:00:01Z")  # sealed
    _plant_unit(store, repo, "X", targets=["p.md"])  # in-flight
    request = compose.build_list_request(root=repo, store=store)

    resolved = resolve_owners(request, "docs/p.md")

    assert isinstance(resolved, ResolvedOwners)
    by_id = {o.unit_id: o for o in resolved.owners}
    assert isinstance(by_id["A"], OwnerRef)
    assert by_id["A"].sealed is True and by_id["A"].accept_at is not None
    assert by_id["X"].sealed is False and by_id["X"].accept_at is None
    assert resolved.winner_id == "X"
    # Winner-only wrapper stays stable for existing callers.
    assert find_unit_by_draft(request, "p.md") == "X"


def test_scan_tolerates_bad_neighbour_resolve(repo, capsys):
    # WR-01: an unreadable (schema-newer) neighbour covering the page is skipped
    # from sealed-eligibility — it holds its lease, is warned about, and never
    # aborts resolution.
    store = FilesystemPlanningStore()
    _plant_unit(store, repo, "A", targets=["p.md"])
    _plant_accept(store, repo, "A", "2026-01-01T00:00:01Z")  # sealed
    _plant_unit(store, repo, "B", targets=["p.md"])
    _plant_corrupt(store, repo, "B")  # schema_version 999 ⇒ unreadable
    request = compose.build_list_request(root=repo, store=store)

    resolved = resolve_owners(request, "p.md")  # must not raise

    by_id = {o.unit_id: o for o in resolved.owners}
    assert set(by_id) == {"A", "B"}
    assert by_id["A"].sealed is True
    # B cannot be proven sealed ⇒ treated as in-flight, keeps its lease (wins).
    assert by_id["B"].sealed is False
    assert resolved.winner_id == "B"
    assert "B" in capsys.readouterr().err  # stderr warning names the skipped unit


# --------------------------------------------------------------------------- #
# Task 1 (Wave 2) — sealed-vs-in-flight split of the declare/edit overlap guard
# + plan_takeovers (OWN-01/OWN-02/OWN-06/WR-01)
# --------------------------------------------------------------------------- #
#
# The overlap guard (`_assert_targets_unclaimed`) no longer refuses ANY overlap:
# it splits on `is_sealed`. An in-flight owner still refuses (it holds its
# lease); a sealed owner is allowed and its supersede is recorded separately by
# `plan_takeovers`. A `_seal(...)` neighbour is stood up via the real path; an
# in-flight neighbour needs only a signoff act (provenance with no verdict yet);
# a sealed multi-target owner is planted directly (the mock driver only drafts
# the primary, so a real multi-page seal is out of scope for these unit tests).


def _plant_sealed(store, root, unit_id, *, targets, at):
    """Plant a unit.md + a sealed provenance whose accept edit seals ``targets``.

    The accept edit carries a :class:`FileDigest` per page (``docs/<t>``), so
    ``plan_takeovers`` can read each page's sealed sha12. Returns the planted
    ``files`` list for digest assertions.
    """
    _plant_unit(store, root, unit_id, targets=targets)
    files = [
        FileDigest(path=f"docs/{t}", sha256=hashlib.sha256(t.encode()).hexdigest())
        for t in targets
    ]
    store.write_provenance(
        Provenance(
            unit_id=unit_id,
            reviewer_edits=[
                ReviewerEdit(
                    at=at,
                    reviewer="Ada",
                    summary="accepted",
                    verdict=ReviewVerdict.accept,
                    files=files,
                )
            ],
        ),
        root=root,
    )
    return files


@pytest.mark.asyncio
async def test_declare_onto_inflight_refuses(repo):
    # OWN-01/D-01: declaring onto a page held by an in-flight (drafted, not
    # accepted) owner refuses, naming the owner id + its derived state.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo, unit="A", sphinx_target="p.md")
    _steer(store, repo, clock, unit="A")
    await _draft(store, repo, clock, unit="A")  # in-flight: drafted, not accepted

    with pytest.raises(TargetClaimedError) as excinfo:
        _declare(store, repo, unit="B", sphinx_target="p.md")

    message = str(excinfo.value)
    assert "A" in message
    assert "not accepted" in message


@pytest.mark.asyncio
async def test_declare_onto_sealed_succeeds(repo):
    # OWN-02/D-01: once A seals (latest verdict accept), it releases its lease —
    # B may claim A's page and the declare succeeds (no raise).
    store = FilesystemPlanningStore()
    clock = _Clock()
    await _seal(store, repo, clock, unit="A", sphinx_target="p.md")

    _declare(store, repo, unit="B", sphinx_target="p.md")  # must not raise

    assert store.load_unit("B", root=repo).sphinx_target == "p.md"


@pytest.mark.asyncio
async def test_extras_lease_parity(repo):
    # OWN-06: the lease scan iterates unit.targets uniformly, so an EXTRA
    # (non-primary) target refuses and supersedes exactly like a primary.
    store = FilesystemPlanningStore()
    clock = _Clock()

    # Refuse leg: an in-flight owner A holds an extra page e.md; a new claim on
    # e.md refuses, just as a primary overlap would.
    _declare(store, repo, unit="A", sphinx_target="a.md", extra_targets=["e.md"])
    _steer(store, repo, clock, unit="A")  # in-flight: signed off, not drafted
    with pytest.raises(TargetClaimedError):
        _declare(store, repo, unit="B", sphinx_target="e.md")

    # Takeover leg: a sealed owner S holds an extra page x.md; plan_takeovers
    # supersedes it identically to a primary.
    files = _plant_sealed(store, repo, "S", targets=["s.md", "x.md"], at="2026-05-05Z")
    takeovers = store.plan_takeovers("N", ["x.md"], root=repo)

    assert [t.owner_id for t in takeovers] == ["S"]
    assert takeovers[0].page == "x.md"
    expected_sha = next(f.sha256 for f in files if f.path == "docs/x.md")
    assert takeovers[0].sealed_sha12 == expected_sha[:12]


def test_scan_tolerates_bad_neighbour(repo, capsys):
    # WR-01: a corrupt/schema-newer neighbour overlapping the claimed page is
    # skipped from the guard (warned, not sealed-eligible) — the declare of the
    # new unit still succeeds with no traceback.
    store = FilesystemPlanningStore()
    _plant_unit(store, repo, "B", targets=["p.md"])
    _plant_corrupt(store, repo, "B")  # schema_version 999 ⇒ unreadable, overlaps

    _declare(store, repo, unit="C", sphinx_target="p.md")  # must not raise

    assert store.load_unit("C", root=repo).sphinx_target == "p.md"
    assert "B" in capsys.readouterr().err  # stderr warning names the skipped unit


def test_plan_takeovers_returns_records(repo):
    # OWN-02: plan_takeovers over a page sealed by A returns one Takeover naming
    # A, the page, the sealed sha12 (first 12 hex of the accept files[] digest),
    # and the accept timestamp.
    store = FilesystemPlanningStore()
    files = _plant_sealed(store, repo, "A", targets=["p.md"], at="2026-01-01T00:00:01Z")

    takeovers = store.plan_takeovers("B", ["p.md"], root=repo)

    assert len(takeovers) == 1
    (takeover,) = takeovers
    assert isinstance(takeover, Takeover)
    assert takeover.page == "p.md"
    assert takeover.owner_id == "A"
    assert takeover.accept_at == "2026-01-01T00:00:01Z"
    assert takeover.sealed_sha12 == files[0].sha256[:12]


# --------------------------------------------------------------------------- #
# Task 2 (Wave 2) — Dogen-Extends trailer + declare/edit thread takeovers into
# the commit (OWN-02, D-05)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_takeover_trailer_recorded(repo):
    # OWN-02/D-05: declaring onto a sealed owner's page records the supersede on
    # the declare commit — a `docs/<page> extends unit <owner> (sealed <sha12>)`
    # body line and a repeatable `Dogen-Extends: <owner>` trailer.
    store = FilesystemPlanningStore()
    clock = _Clock()
    seam = GitRepoSeam()
    await _seal(store, repo, clock, unit="A", sphinx_target="p.md", repo=seam)

    _declare(store, repo, unit="B", sphinx_target="p.md", repo=seam)

    message = _head_message(repo)
    assert "Dogen-Extends: A" in message
    assert "docs/p.md extends unit A (sealed " in message


@pytest.mark.asyncio
async def test_multi_owner_repeated_trailers(repo):
    # D-05: a single declare overlapping two distinct sealed owners records two
    # repeated `Dogen-Extends:` trailers and one extends: body line each (git
    # -idiomatic, like Co-Authored-By).
    store = FilesystemPlanningStore()
    clock = _Clock()
    seam = GitRepoSeam()
    await _seal(store, repo, clock, unit="A", sphinx_target="p.md", repo=seam)
    await _seal(store, repo, clock, unit="C", sphinx_target="q.md", repo=seam)

    # B claims p.md (sealed by A) as primary and q.md (sealed by C) as an extra.
    _declare(
        store, repo, unit="B", sphinx_target="p.md", extra_targets=["q.md"], repo=seam
    )

    message = _head_message(repo)
    assert message.count("Dogen-Extends:") == 2
    assert "Dogen-Extends: A" in message
    assert "Dogen-Extends: C" in message
    assert "docs/p.md extends unit A (sealed " in message
    assert "docs/q.md extends unit C (sealed " in message


@pytest.mark.asyncio
async def test_edit_onto_sealed_records_takeover(repo):
    # OWN-02: editing an existing unit to add a target sealed by another owner
    # records the same note/extends/trailer at the edit commit.
    store = FilesystemPlanningStore()
    clock = _Clock()
    seam = GitRepoSeam()
    await _seal(store, repo, clock, unit="A", sphinx_target="p.md", repo=seam)
    # B starts on its own page, then edits to also target A's sealed page.
    _declare(store, repo, unit="B", sphinx_target="b.md", repo=seam)

    edit_unit(
        compose.build_edit_request(
            "B", root=repo, store=store, add_targets=["p.md"], repo=seam
        )
    )

    message = _head_message(repo)
    assert "Dogen-Extends: A" in message
    assert "docs/p.md extends unit A (sealed " in message
