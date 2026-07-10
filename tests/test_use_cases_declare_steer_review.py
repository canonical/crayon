"""Domain-level behaviour tests for the promoted declare/steer/review use-cases.

These exercise the three use-cases promoted out of mvp-1's Typer CLI into
``core/`` (D-01/D-02). They run against a *real*
:class:`FilesystemPlanningStore` over a tmp dir with an injected deterministic
clock and a stub :data:`Identity` callable — the host boundaries (git config,
the wall clock) are injected so the domain stays deterministic and the WR-04 /
WR-05 guards are proven as core invariants, not CLI ceremony.
"""

from pathlib import Path

import pytest

from dogen.adapters.planning_fs import (
    FilesystemPlanningStore,
    UnitExistsError,
    split_front_matter,
)
from dogen.core.models import (
    Effort,
    FileDigest,
    Generation,
    Intent,
    ProgressState,
    Provenance,
    Signoff,
    Unit,
    derive_progress,
)
from dogen.core.orchestrator import (
    DeclareRequest,
    NotDraftedError,
    ReviewRequest,
    SignoffExistsError,
    SignoffRequest,
    declare,
    review,
)
from dogen.core.orchestrator import (
    signoff as steer,
)


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


def _identity() -> tuple[str, str]:
    """Return a stub git identity for the injected Identity port."""
    return ("Ada Lovelace", "ada@example.com")


def _store_with_unit(
    root: Path, *, intent: Intent = Intent.reference, audience: str = "devs"
) -> FilesystemPlanningStore:
    """Scaffold unit ``u`` under ``root`` and return the backing store."""
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=intent, audience=audience)
    return store


# --------------------------------------------------------------------------- #
# declare (UNIT-01)
# --------------------------------------------------------------------------- #


def test_declare_creates_unit_md(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    request = DeclareRequest(
        unit_id="u",
        root=tmp_path,
        store=store,
        intent=Intent.reference,
        audience="developers",
    )
    written = declare(request)
    assert written.exists()
    assert written == tmp_path / ".dogen" / "units" / "u" / "unit.md"
    front, _ = split_front_matter(written.read_text(encoding="utf-8"))
    unit = Unit(**front)
    assert unit.unit_id == "u"
    assert unit.intent is Intent.reference
    assert unit.audience == "developers"


def test_declare_clobber_raises_unit_exists(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    written = tmp_path / ".dogen" / "units" / "u" / "unit.md"
    written.write_text(written.read_text() + "\nedited\n", encoding="utf-8")
    with pytest.raises(UnitExistsError):
        declare(DeclareRequest(unit_id="u", root=tmp_path, store=store))
    # The clobber refusal must leave the prior hand-edited file untouched.
    assert "edited" in written.read_text(encoding="utf-8")


def test_declare_force_overwrites(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    written = tmp_path / ".dogen" / "units" / "u" / "unit.md"
    written.write_text(written.read_text() + "\nedited\n", encoding="utf-8")
    declare(DeclareRequest(unit_id="u", root=tmp_path, store=store, force=True))
    assert "edited" not in written.read_text(encoding="utf-8")


def test_declare_unsafe_id_raises_value_error(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    with pytest.raises(ValueError):
        declare(DeclareRequest(unit_id="../escape", root=tmp_path, store=store))


# --------------------------------------------------------------------------- #
# steer (UNIT-02, WR-04)
# --------------------------------------------------------------------------- #


def _steer_request(
    root: Path,
    store: FilesystemPlanningStore,
    clock: _Clock,
    *,
    force: bool = False,
) -> SignoffRequest:
    """Build a SignoffRequest wired to the stub identity and a given clock."""
    return SignoffRequest(
        unit_id="u",
        root=root,
        store=store,
        identity=_identity,
        now=clock,
        force=force,
    )


def test_steer_records_steering(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path, intent=Intent.reference, audience="devs")
    warn = steer(_steer_request(tmp_path, store, _Clock()))
    assert warn is False
    provenance = store.read_provenance("u", root=tmp_path)
    assert provenance.signoff is not None
    assert provenance.signoff.author == "Ada Lovelace"
    assert provenance.signoff.intent is Intent.reference
    assert provenance.signoff.audience == "devs"


def test_steer_refuses_resteer_without_force(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    clock = _Clock()
    steer(_steer_request(tmp_path, store, clock))
    recorded = store.read_provenance("u", root=tmp_path).signoff
    assert recorded is not None
    with pytest.raises(SignoffExistsError):
        steer(_steer_request(tmp_path, store, clock))
    # WR-04: the refusal writes nothing — the recorded steering is unchanged.
    after = store.read_provenance("u", root=tmp_path).signoff
    assert after is not None
    assert after.at == recorded.at
    assert after.author == recorded.author


def test_steer_force_overwrites_and_warns(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    # Seed a unit that has already been steered AND drafted (one generation),
    # so a forced re-steer must honour the overwrite but flag the warn signal:
    # the existing generation predates the new steering act.
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Prior",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            generations=[
                Generation(
                    model="m",
                    model_version="v",
                    effort=Effort.medium,
                    tooling_version="0.0.0",
                    sdk="sdk",
                    files=[FileDigest(path="docs/u.md", sha256="ab12")],
                    run_id="r",
                    at="2026-01-01T00:00:01Z",
                    action="draft",
                )
            ],
        ),
        root=tmp_path,
    )
    warn = steer(_steer_request(tmp_path, store, _Clock(), force=True))
    assert warn is True
    steering = store.read_provenance("u", root=tmp_path).signoff
    assert steering is not None
    assert steering.author == "Ada Lovelace"
    assert steering.at != "2026-01-01T00:00:00Z"


def test_steer_at_precedes_a_later_generation(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    clock = _Clock()
    steer(_steer_request(tmp_path, store, clock))
    steering = store.read_provenance("u", root=tmp_path).signoff
    assert steering is not None
    # A later draft would stamp generations[0].at from a subsequent clock tick;
    # the recorded steering.at must order strictly before it (the WR-04 ordering).
    later = clock()
    assert steering.at < later


# --------------------------------------------------------------------------- #
# review (REVIEW-01/02, WR-05, D-06)
# --------------------------------------------------------------------------- #


def _review_request(
    root: Path,
    store: FilesystemPlanningStore,
    clock: _Clock,
    *,
    note: str = "tightened the intro",
) -> ReviewRequest:
    """Build a ReviewRequest wired to the stub identity and a given clock."""
    return ReviewRequest(
        unit_id="u",
        root=root,
        store=store,
        identity=_identity,
        now=clock,
        note=note,
    )


def _seed_drafted(store: FilesystemPlanningStore, root: Path) -> None:
    """Seed a steered + drafted unit (provenance with one landed generation).

    PROV-04: the drafted state is derived from the recorded generation; no
    ``progress.yaml`` is seeded.
    """
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada Lovelace",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            generations=[
                Generation(
                    model="m",
                    model_version="v",
                    effort=Effort.medium,
                    tooling_version="0.0.0",
                    sdk="",
                    files=[FileDigest(path="docs/u.md", sha256="ab12")],
                    run_id="r",
                    at="2026-01-01T00:00:01Z",
                    action="draft",
                )
            ],
        ),
        root=root,
    )


def test_review_appends_edit_and_sets_reviewed(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    _seed_drafted(store, tmp_path)
    review(_review_request(tmp_path, store, _Clock(), note="fixed a typo"))
    provenance = store.read_provenance("u", root=tmp_path)
    assert len(provenance.reviewer_edits) == 1
    assert provenance.reviewer_edits[0].reviewer == "Ada Lovelace"
    assert provenance.reviewer_edits[0].summary == "fixed a typo"
    # PROV-04: reviewed state derives from the record — the landed reviewer edit
    # now outnumbers the latest generation's reviewer_edit_count snapshot.
    assert derive_progress(provenance) is ProgressState.reviewed


def test_review_is_idempotent_stays_reviewed(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    _seed_drafted(store, tmp_path)
    clock = _Clock()
    review(_review_request(tmp_path, store, clock, note="first pass"))
    review(_review_request(tmp_path, store, clock, note="second pass"))
    provenance = store.read_provenance("u", root=tmp_path)
    # Each review records its own edit...
    assert len(provenance.reviewer_edits) == 2
    # ...but the derived state stays reviewed idempotently (WR-05 falls out of the
    # count-based rule — no separately-stamped transition to double up).
    assert derive_progress(provenance) is ProgressState.reviewed


def test_review_before_draft_raises_not_drafted(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    # Steered (provenance written) but never drafted: no recorded generation, so
    # NotDraftedError now keys on empty provenance.generations (not a missing file).
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada Lovelace",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
        ),
        root=tmp_path,
    )
    with pytest.raises(NotDraftedError):
        review(_review_request(tmp_path, store, _Clock()))


def test_review_never_sets_committed(tmp_path: Path) -> None:
    store = _store_with_unit(tmp_path)
    _seed_drafted(store, tmp_path)
    review(_review_request(tmp_path, store, _Clock()))
    # PROV-04: the derived vocabulary is pending|drafted|reviewed only —
    # publishing (committed) is never a state the loop can reach (SKEL-03/D-38).
    provenance = store.read_provenance("u", root=tmp_path)
    assert derive_progress(provenance) is ProgressState.reviewed
