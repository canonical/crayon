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

import subprocess

import pytest

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
from dogen.core.models import (
    Intent,
    Provenance,
    ReviewerEdit,
    ReviewVerdict,
    _latest_accept_at,
    is_sealed,
)
from dogen.core.orchestrator import (
    OwnerRef,
    ResolvedOwners,
    declare,
    draft,
    find_unit_by_draft,
    resolve_owners,
    review,
)
from dogen.core.orchestrator import (
    signoff as steer,
)


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


def _declare(store, root, *, unit="u", sphinx_target=None, extra_targets=None):
    declare(
        compose.build_declare_request(
            unit,
            root=root,
            store=store,
            intent=Intent.reference,
            audience="devs",
            sphinx_target=sphinx_target,
            extra_targets=extra_targets,
        )
    )


def _steer(store, root, clock, *, unit="u", force=False):
    return steer(
        compose.build_signoff_request(
            unit, root=root, store=store, now=clock, force=force
        )
    )


async def _draft(store, root, clock, *, unit="u"):
    return (
        await draft(
            compose.build_draft_request(unit, root=root, store=store, now=clock)
        )
    ).path


def _review(  # noqa: PLR0913
    store, root, clock, note, *, unit="u", verdict=ReviewVerdict.fix
):
    return review(
        compose.build_review_request(
            unit, root=root, store=store, note=note, now=clock, verdict=verdict
        )
    )


async def _seal(  # noqa: PLR0913
    store, root, clock, *, unit="A", sphinx_target=None, extra_targets=None
):
    """Drive declare→steer→draft→review-accept for ``unit`` and return its id.

    The shared fixture later waves reuse to stand up a sealed neighbour on
    disk: the unit's latest verdict is ``accept`` (D-01), so it releases its
    lease on the pages in ``unit.targets``.
    """
    _declare(
        store,
        root,
        unit=unit,
        sphinx_target=sphinx_target,
        extra_targets=extra_targets,
    )
    _steer(store, root, clock, unit=unit)
    await _draft(store, root, clock, unit=unit)
    _review(store, root, clock, "accepted", unit=unit, verdict=ReviewVerdict.accept)
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
        Provenance(unit_id=unit_id, reviewer_edits=[_edit(at, verdict=ReviewVerdict.accept)]),
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
